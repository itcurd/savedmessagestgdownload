# Скрипт выгрузки ссылок из «Избранного» в Telegram в Excel-таблицу.

Проходит по истории вашего чата «Избранное», находит сообщения со ссылками, для каждой ссылки получает домен и описание сайта (`<title>` + `meta description`), складывает всё в `.xlsx`, и помечает обработанные сообщения реакцией — чтобы визуально было видно, что уже перенесено.

## Возможности

- Работает от вашего личного аккаунта Telegram (через [Telethon](https://github.com/LonamiWebs/Telethon)), а не через bot-аккаунт — только так можно читать «Избранное».
- Достаёт ссылки из сообщения как через Telegram-сущности (entities), так и через регулярку — на случай нестандартной разметки.
- Для каждой ссылки чистит домен (без `http(s)://`, без `www.`) и подтягивает `<title>` / `meta description` страницы.
- Список доменов-исключений (`EXCLUDED_DOMAINS`): для них описание не запрашивается (по умолчанию — GitHub и сам Telegram), но домен всё равно попадает в таблицу.
- Помечает обработанные сообщения реакцией. Если эмодзи из конфига недоступно как обычная реакция, скрипт пробует поставить его как кастомную emoji-реакцию (нужен Telegram Premium), а если и это невозможно — откатывается на запасной эмодзи.
- Скрипт можно безопасно перезапускать: уже помеченные сообщения пропускаются.
- Устойчив к ошибкам — таймаут, недоступный сайт или сбой на одном сообщении не обрывают весь процесс, результат сохраняется даже при аварийном завершении.

## Требования

- Python 3.11+
- Аккаунт Telegram и API-ключи с [my.telegram.org](https://my.telegram.org)

## Установка

```bash
git clone https://github.com/itcurdev/saved-links-exporter.git
cd saved-links-exporter
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка

1. Получите `api_id` и `api_hash`:
   - зайдите на [my.telegram.org](https://my.telegram.org) и войдите по своему номеру телефона;
   - откройте раздел **API development tools**;
   - заполните форму (название приложения — любое) и сохраните появившиеся `api_id` и `api_hash`.
2. Скопируйте пример конфига и заполните его:
   ```bash
   cp .env.example .env
   ```
3. Откройте `.env` и укажите свои значения:

| Переменная | Описание |
|---|---|
| `API_ID`, `API_HASH` | ключи с my.telegram.org |
| `PHONE` | номер телефона в международном формате |
| `SESSION_NAME` | имя файла сессии Telethon (создаётся автоматически) |
| `OUTPUT_XLSX` | путь к итоговому файлу таблицы |
| `MESSAGE_LIMIT` | сколько последних сообщений просматривать (`0` — все) |
| `HTTP_TIMEOUT` | таймаут запроса к сайту, сек |
| `REQUEST_DELAY` | пауза между запросами к сайтам, сек |
| `REACTION_EMOJI` | эмодзи-реакция для обработанных сообщений |
| `EXCLUDED_DOMAINS` | домены, для которых не нужно ходить за описанием (через запятую) |

## Запуск

```bash
python main.py
```

При первом запуске Telethon запросит код подтверждения (придёт в само приложение Telegram, не SMS) и, если включена двухфакторная аутентификация, облачный пароль. После успешного входа создастся файл сессии — при повторных запусках вход больше не потребуется.

## Важно

- Файл сессии (`*.session`) даёт полный доступ к вашему аккаунту Telegram — никогда не публикуйте и не коммитьте его (уже добавлен в `.gitignore`).
- То же самое касается `.env` с вашими ключами.
- Итоговый `.xlsx` содержит ваши личные ссылки и тоже исключён из репозитория по умолчанию.
# ENG 
## A script for exporting links from Telegram’s ‘Favourites’ to an Excel spreadsheet.

It scans the history of your ‘Favourites’ chat, finds messages containing links, retrieves the domain and website description (`<title>` + `meta description`) for each link, compiles everything into an `.xlsx` file, and marks the processed messages with a reaction — so you can see at a glance which ones have already been transferred.

## Features

- Runs from your personal Telegram account (via [Telethon](https://github.com/LonamiWebs/Telethon)), rather than a bot account — this is the only way to access ‘Favourites’.
- Extracts links from messages using both Telegram entities and regular expressions — in case of non-standard markup.
- For each link, it strips the domain (removing `http(s)://` and `www.`) and fetches the page’s `<title>` and `meta description`.
- List of excluded domains (`EXCLUDED_DOMAINS`): descriptions are not fetched for these (by default, GitHub and Telegram itself), but the domain is still added to the table.
- Marks processed messages with a reaction. If an emoji from the configuration is not available as a standard reaction, the script attempts to set it as a custom emoji reaction (Telegram Premium required); if this is also impossible, it falls back to a default emoji.
- The script can be safely restarted: messages that have already been marked are skipped.
- Error-resilient — a timeout, an unavailable website or a failure on a single message will not interrupt the entire process; the result is saved even in the event of an abnormal termination.

## Requirements

- Python 3.11+
- A Telegram account and API keys from [my.telegram.org](https://my.telegram.org)

## Installation

```bash
git clone https://github.com/itcurdev/saved-links-exporter.git
cd saved-links-exporter
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

1. Obtain your `api_id` and `api_hash`:
   - go to [my.telegram.org](https://my.telegram.org) and log in using your phone number;
   - open the **API development tools** section;
   - fill in the form (you can use any name for the application) and save the `api_id` and `api_hash` that appear.
2. Copy the example configuration file and fill it in:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and specify your own values:

| Variable | Description |
|---|---|
| `API_ID`, `API_HASH` | keys from my.telegram.org |
| `PHONE` | phone number in international format |
| `SESSION_NAME` | Telethon session filename (created automatically) |
| `OUTPUT_XLSX` | path to the final spreadsheet file |
| `MESSAGE_LIMIT` | number of recent messages to view (`0` — all) |
| `HTTP_TIMEOUT` | request timeout to the website, in seconds |
| `REQUEST_DELAY` | pause between requests to websites, in seconds |
| `REACTION_EMOJI` | reaction emoji for processed messages |
| `EXCLUDED_DOMAINS` | domains for which descriptions do not need to be fetched (separated by commas) |

## Running the programme

```bash
python main.py
```

The first time you run Telethon, it will ask for a verification code (sent to the Telegram app itself, not via SMS) and, if two-factor authentication is enabled, your cloud password. Once you have logged in successfully, a session file will be created — you will not need to log in again on subsequent runs.

## Important

- The session file (`*.session`) grants full access to your Telegram account — never publish or commit it (it’s already added to `.gitignore`).
- The same applies to `.env`, which contains your keys.
- The resulting `.xlsx` file contains your personal links and is also excluded from the repository by default.
