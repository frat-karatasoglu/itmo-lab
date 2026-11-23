"""Одноразовая инициализация схемы БД.

В docker compose запускается отдельным init-сервисом `migrate`
(`python -m app.migrate`) до старта API и завершается с кодом 0.
Скрипт идемпотентен: повторный запуск ничего не ломает.
"""

import sys

from app import db


def main() -> int:
    print(f"[migrate] backend: {db.backend_name()}", flush=True)
    db.init_schema()
    count = db.fetch_one("SELECT COUNT(*) AS n FROM notes")["n"]
    print(f"[migrate] schema is up to date, notes in table: {count}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
