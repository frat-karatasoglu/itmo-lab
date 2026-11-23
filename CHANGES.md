# CHANGES

## ЛР 2. Docker Compose

- Добавлен `docker-compose.yml` из трёх сервисов: `db` (PostgreSQL 16),
  `migrate` (одноразовый init-сервис) и `app` (Notes API).
- Все переменные окружения вынесены в `.env`, а `.env` добавлен в `.dockerignore`.
- Приложение умеет работать с PostgreSQL (`app/db.py`). Если `DB_HOST` не задан,
  оно, как и в ЛР 1, использует SQLite в `DATA_DIR`.
- Создание схемы БД вынесено в `app/migrate.py` (`python -m app.migrate`).
- В `requirements.txt` добавлен `psycopg[binary]==3.3.7`. Эта версия выбрана,
  потому что у неё есть готовые wheel-пакеты и для Python 3.12
  (`Dockerfile.good`), и для Python 3.15, который сейчас приходит с
  `python:latest` (`Dockerfile.bad`).
- Версия API: 2.0.0. Поле `created_at` теперь отдаётся в формате ISO 8601.

## ЛР 1. Dockerfile

- Notes API на FastAPI с хранением заметок в SQLite.
- `Dockerfile.good`, `Dockerfile.bad`, `.dockerignore`, README с разбором практик.
