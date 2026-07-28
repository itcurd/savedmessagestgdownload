import os
import re
import asyncio
import logging

from urllib.parse import urlparse

import httpx
import openpyxl
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.tl.types import (
    MessageEntityUrl,
    MessageEntityTextUrl,
    ReactionEmoji,
    ReactionCustomEmoji,
    AvailableReaction,
    InputStickerSetEmojiGenericAnimations,
)
from telethon.tl.types.messages import AvailableReactions
from telethon.tl.functions.messages import (
    SendReactionRequest,
    GetAvailableReactionsRequest,
    GetStickerSetRequest,
)
from telethon.errors import FloodWaitError, RPCError

FALLBACK_REACTION_EMOJI = "💩"

URL_REGEX = re.compile(r"https?://[^\s]+")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("saved_links")


def _utf16_slice(text: str, offset: int, length: int) -> str:
    raw = text.encode("utf-16-le")
    start, end = offset * 2, (offset + length) * 2
    return raw[start:end].decode("utf-16-le")


def extract_urls(message) -> set[str]:
    urls: set[str] = set()

    if message.entities and message.text:
        for entity in message.entities:
            if isinstance(entity, MessageEntityTextUrl):
                urls.add(entity.url)
            elif isinstance(entity, MessageEntityUrl):
                urls.add(_utf16_slice(message.text, entity.offset, entity.length))

    if message.text:
        urls.update(URL_REGEX.findall(message.text))

    return urls


def clean_domain(url: str) -> str:
    normalized = url if "://" in url else f"http://{url}"
    netloc = urlparse(normalized).netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.lower()


async def fetch_page_meta(url: str, http_client: httpx.AsyncClient, timeout: float) -> str:
    full_url = url if url.startswith(("http://", "https://")) else f"https://{url}"

    try:
        response = await http_client.get(
            full_url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SavedLinksExporter/1.0)"},
        )
        response.raise_for_status()
    except httpx.TimeoutException:
        return "Сайт не ответил за отведённое время (таймаут)"
    except httpx.HTTPStatusError as e:
        return f"Сайт вернул ошибку HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return f"Не удалось подключиться к сайту ({e.__class__.__name__})"
    except Exception as e:
        return f"Неизвестная ошибка при обращении к сайту: {e}"

    try:
        soup = BeautifulSoup(response.text, "lxml")
    except Exception:
        return "Не удалось разобрать HTML страницы"

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()
    if not description:
        meta_og = soup.find("meta", attrs={"property": "og:description"})
        if meta_og and meta_og.get("content"):
            description = meta_og["content"].strip()

    if title and description:
        return f"{title} — {description}"
    if title:
        return title
    if description:
        return description
    return "Описание не найдено (нет ни title, ни meta description)"


def parse_excluded_domains(raw: str) -> set[str]:
    return {clean_domain(item.strip()) for item in raw.split(",") if item.strip()}


def is_excluded(domain: str, excluded_domains: set[str]) -> bool:
    return any(domain == exc or domain.endswith(f".{exc}") for exc in excluded_domains)


async def resolve_reaction(client: TelegramClient, desired_emoji: str):
    try:
        available = await client(GetAvailableReactionsRequest(hash=0))
        if isinstance(available, AvailableReactions):
            valid_emoji = {
                r.reaction
                for r in available.reactions
                if isinstance(r, AvailableReaction) and not r.inactive
            }
            if desired_emoji in valid_emoji:
                log.info("Эмодзи %s доступно как обычная реакция", desired_emoji)
                return ReactionEmoji(emoticon=desired_emoji)
    except Exception as e:
        log.warning("Не удалось получить список обычных реакций: %s", e)

    try:
        sticker_set = await client(
            GetStickerSetRequest(stickerset=InputStickerSetEmojiGenericAnimations(), hash=0)
        )
        for pack in sticker_set.packs:
            if pack.emoticon == desired_emoji and pack.documents:
                log.info(
                    "Эмодзи %s недоступно как обычная реакция, использую кастомную "
                    "emoji-реакцию (требуется Telegram Premium на аккаунте)",
                    desired_emoji,
                )
                return ReactionCustomEmoji(document_id=pack.documents[0])
    except Exception as e:
        log.warning("Не удалось получить кастомную emoji-реакцию для %s: %s", desired_emoji, e)

    log.warning(
        "Эмодзи %s недоступно ни как обычная, ни как кастомная реакция. Использую %s вместо него.",
        desired_emoji,
        FALLBACK_REACTION_EMOJI,
    )
    return ReactionEmoji(emoticon=FALLBACK_REACTION_EMOJI)


def already_tagged(message, reaction) -> bool:
    if not message.reactions or not message.reactions.results:
        return False
    for reaction_count in message.reactions.results:
        r = reaction_count.reaction
        if (
            isinstance(reaction, ReactionEmoji)
            and isinstance(r, ReactionEmoji)
            and r.emoticon == reaction.emoticon
        ):
            return True
        if (
            isinstance(reaction, ReactionCustomEmoji)
            and isinstance(r, ReactionCustomEmoji)
            and r.document_id == reaction.document_id
        ):
            return True
    return False


async def react_trash(client: TelegramClient, message, reaction) -> None:
    try:
        await client(
            SendReactionRequest(
                peer=message.peer_id,
                msg_id=message.id,
                reaction=[reaction],
                big=False,
                add_to_recent=False,
            )
        )
    except FloodWaitError as e:
        log.warning("Флуд-контроль Telegram: жду %s сек перед повторной реакцией", e.seconds)
        await asyncio.sleep(e.seconds)
        await react_trash(client, message, reaction)
    except RPCError as e:
        log.warning("Не удалось поставить реакцию на сообщение %s: %s", message.id, e)


async def main() -> None:
    load_dotenv()

    api_id = int(os.environ["API_ID"])
    api_hash = os.environ["API_HASH"]
    phone = os.environ["PHONE"]
    session_name = os.getenv("SESSION_NAME", "saved_messages_session")
    output_path = os.getenv("OUTPUT_XLSX", "saved_links.xlsx")
    message_limit = int(os.getenv("MESSAGE_LIMIT", "0")) or None
    http_timeout = float(os.getenv("HTTP_TIMEOUT", "10"))
    request_delay = float(os.getenv("REQUEST_DELAY", "1"))
    reaction_emoji_str = os.getenv("REACTION_EMOJI", "🗑")
    excluded_domains = parse_excluded_domains(os.getenv("EXCLUDED_DOMAINS", ""))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Saved Links"
    ws.append(["Домен", "Описание"])
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 100

    rows_added = 0
    messages_processed = 0

    client = TelegramClient(session_name, api_id, api_hash)

    try:
        await client.start(phone=phone)
        log.info("Авторизация в Telegram прошла успешно")

        resolved_reaction = await resolve_reaction(client, reaction_emoji_str)

        async with httpx.AsyncClient() as http_client:
            async for message in client.iter_messages("me", limit=message_limit):
                try:
                    if already_tagged(message, resolved_reaction):
                        continue

                    urls = extract_urls(message)
                    if not urls:
                        continue

                    message_had_success = False
                    for url in urls:
                        domain = clean_domain(url)
                        if not domain:
                            continue

                        if is_excluded(domain, excluded_domains):
                            log.info("Домен %s в списке исключений - пропускаю запрос и реакцию", domain)
                            description = "Домен в списке исключений (EXCLUDED_DOMAINS) - описание не запрашивалось"
                            ws.append([domain, description])
                            rows_added += 1
                            continue

                        log.info("Обрабатываю ссылку: %s", domain)
                        description = await fetch_page_meta(url, http_client, http_timeout)
                        await asyncio.sleep(request_delay)

                        ws.append([domain, description])
                        rows_added += 1
                        message_had_success = True

                    if message_had_success:
                        await react_trash(client, message, resolved_reaction)
                        messages_processed += 1
                        await asyncio.sleep(0.5)

                except Exception as e:
                    log.error("Ошибка при обработке сообщения %s: %s", getattr(message, "id", "?"), e)
                    continue

    except Exception as e:
        log.error("Критическая ошибка выполнения: %s", e)

    finally:
        wb.save(output_path)
        log.info(
            "Готово. Сообщений помечено: %s, строк добавлено: %s. Файл: %s",
            messages_processed,
            rows_added,
            output_path,
        )
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
