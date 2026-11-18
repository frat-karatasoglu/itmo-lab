"""Notes API — простой REST-сервис заметок.

Данные хранятся в SQLite-файле в каталоге DATA_DIR. В контейнере этот
каталог монтируется как volume, поэтому заметки переживают пересоздание
контейнера. Позже SQLite можно заменить на PostgreSQL (ЛР 2+).
"""

import os
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_VERSION = "1.0.0"
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DB_PATH = DATA_DIR / "notes.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Notes API", version=APP_VERSION, lifespan=lifespan)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class Note(NoteIn):
    id: int
    created_at: str


@app.get("/")
def root() -> dict:
    return {"service": "notes-api", "version": APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health() -> dict:
    with closing(get_conn()) as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/notes", response_model=list[Note])
def list_notes() -> list[dict]:
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM notes ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/notes", response_model=Note, status_code=201)
def create_note(note: NoteIn) -> dict:
    with closing(get_conn()) as conn, conn:
        cur = conn.execute("INSERT INTO notes (text) VALUES (?)", (note.text,))
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.get("/notes/{note_id}", response_model=Note)
def get_note(note_id: int) -> dict:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return dict(row)


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int) -> None:
    with closing(get_conn()) as conn, conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Note not found")
