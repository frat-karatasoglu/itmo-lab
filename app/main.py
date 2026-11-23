"""Notes API — простой REST-сервис заметок.

Хранилище выбирается переменными окружения (см. app/db.py):
* ЛР 1: SQLite-файл в DATA_DIR, каталог монтируется как volume;
* ЛР 2: PostgreSQL в отдельном контейнере, схему создаёт init-сервис `migrate`.
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import db

APP_VERSION = "2.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # С PostgreSQL схему создаёт init-сервис migrate.
    # В режиме одного контейнера (SQLite) приложение делает это само.
    if not db.is_postgres():
        db.init_schema()
    yield


app = FastAPI(title="Notes API", version=APP_VERSION, lifespan=lifespan)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class Note(NoteIn):
    id: int
    created_at: datetime


@app.get("/")
def root() -> dict:
    return {
        "service": "notes-api",
        "version": APP_VERSION,
        "storage": db.backend_name(),
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    db.fetch_one("SELECT 1 AS ok")
    return {"status": "ok", "storage": db.backend_name()}


@app.get("/notes", response_model=list[Note])
def list_notes() -> list[dict]:
    return db.fetch_all("SELECT id, text, created_at FROM notes ORDER BY id")


@app.post("/notes", response_model=Note, status_code=201)
def create_note(note: NoteIn) -> dict:
    return db.fetch_one(
        "INSERT INTO notes (text) VALUES (%s) RETURNING id, text, created_at",
        (note.text,),
    )


@app.get("/notes/{note_id}", response_model=Note)
def get_note(note_id: int) -> dict:
    row = db.fetch_one("SELECT id, text, created_at FROM notes WHERE id = %s", (note_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return row


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int) -> None:
    if db.execute("DELETE FROM notes WHERE id = %s", (note_id,)) == 0:
        raise HTTPException(status_code=404, detail="Note not found")
