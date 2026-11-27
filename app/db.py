"""Слой доступа к БД.

Два режима:
* задан DB_HOST  -> PostgreSQL (ЛР 2, docker compose);
* DB_HOST не задан -> SQLite-файл в DATA_DIR (ЛР 1, один контейнер + volume).

SQL пишется с плейсхолдерами %s; для SQLite они заменяются на ?.
"""

import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

DB_HOST = os.getenv("DB_HOST")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS notes (
    id         SERIAL PRIMARY KEY,
    text       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def is_postgres() -> bool:
    return bool(DB_HOST)


def backend_name() -> str:
    return "postgres" if is_postgres() else "sqlite"


@contextmanager
def _cursor():
    """Курсор, строки которого — dict. Транзакция коммитится при выходе."""
    if is_postgres():
        import psycopg
        from psycopg.rows import dict_row

        conninfo = psycopg.conninfo.make_conninfo(
            host=DB_HOST,
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=5,
        )
        with psycopg.connect(conninfo, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                yield cur
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(DATA_DIR / "notes.db")) as conn, conn:
            conn.row_factory = sqlite3.Row
            yield conn.cursor()


def _sql(query: str) -> str:
    return query if is_postgres() else query.replace("%s", "?")


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    with _cursor() as cur:
        cur.execute(_sql(query), params)
        return [dict(r) for r in cur.fetchall()]


def fetch_one(query: str, params: tuple = ()) -> dict | None:
    with _cursor() as cur:
        cur.execute(_sql(query), params)
        row = cur.fetchone()
        return dict(row) if row is not None else None


def execute(query: str, params: tuple = ()) -> int:
    """Выполняет запрос и возвращает число затронутых строк."""
    with _cursor() as cur:
        cur.execute(_sql(query), params)
        return cur.rowcount


# Произвольный, но постоянный ключ advisory-блокировки для миграций
MIGRATION_LOCK_KEY = 2024_0001


def init_schema() -> None:
    if not is_postgres():
        execute(SCHEMA_SQLITE)
        return
    # Несколько реплик (например, init-контейнеры двух подов в Kubernetes) могут
    # запустить миграцию одновременно. Параллельные CREATE TABLE IF NOT EXISTS
    # в PostgreSQL иногда падают с ошибкой уникальности в системном каталоге,
    # поэтому миграция выполняется под транзакционной advisory-блокировкой:
    # второй процесс ждёт, пока первый закоммитит, и видит готовую таблицу.
    with _cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_KEY,))
        cur.execute(SCHEMA_POSTGRES)
