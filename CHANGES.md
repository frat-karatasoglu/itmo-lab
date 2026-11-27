# CHANGES

## ЛР 3. Kubernetes

- Добавлен каталог `k8s/` с манифестами Nextcloud + PostgreSQL на основе примера из задания.
- `POSTGRES_USER` и `POSTGRES_PASSWORD` перенесены из ConfigMap в Secret `postgres-secret`.
- Переменные Nextcloud перенесены из Deployment в ConfigMap `nextcloud-configmap`.
- Для Nextcloud добавлены `startupProbe`, `livenessProbe` и `readinessProbe` (`/status.php`).
- Service БД переведён на ClusterIP, лимит памяти Nextcloud поднят до 768Mi,
  Service Nextcloud описан манифестом `nextcloud_service.yml`.
- В README добавлен раздел «ЛР 3» с описанием изменений и ответами на вопросы.
- Добавлен раздел «Ход работы» с реальным выводом команд, скриншотами
  `screenshots/lab3-*.png` и проверкой эксперимента `scale postgres` 0 → 1.

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
- В README добавлены разделы «Описание docker-compose.yml» и «Ответы на вопросы»,
  а также результаты локального запуска и скриншоты `screenshots/lab2-*.png`.

## ЛР 1. Dockerfile

- Notes API на FastAPI с хранением заметок в SQLite.
- `Dockerfile.good`, `Dockerfile.bad`, `.dockerignore`, README с разбором практик.
