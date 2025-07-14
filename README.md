# Телеграм-бот для проверки лабораторных работ
## Запуск
Заполнить файл `.env` в корне проекта по примеру ниже.
```env
BOT_TOKEN=
SERVER_BASE_URL=http://host.docker.internal:8000
DB_PATH=/data/db.sqlite
```
В терминале выполнить:
```bash
docker compose up --build
```
