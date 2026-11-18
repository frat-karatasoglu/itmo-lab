# ЛР 1. Dockerfile

**Команда:** Firat Karatasoglu, Yahya

## Приложение

**Notes API** — небольшой REST-сервис заметок на FastAPI. Заметки хранятся в
SQLite-файле в каталоге `/app/data`, который монтируется как **volume**, —
поэтому данные не теряются при пересоздании контейнера.

Приложение выбрано с расчётом на следующие лабораторные: SQLite легко
заменить на PostgreSQL, конфигурация передаётся через переменные окружения,
а эндпоинт `/health` пригодится для liveness/readiness probe в Kubernetes.

| Метод    | Путь           | Описание                     |
|----------|----------------|------------------------------|
| `GET`    | `/`            | Информация о сервисе         |
| `GET`    | `/health`      | Проверка состояния           |
| `GET`    | `/notes`       | Список заметок               |
| `POST`   | `/notes`       | Создать заметку `{"text": "..."}` |
| `GET`    | `/notes/{id}`  | Получить заметку             |
| `DELETE` | `/notes/{id}`  | Удалить заметку              |
| `GET`    | `/docs`        | Swagger UI                   |

## Структура репозитория

```
.
├── app/
│   ├── __init__.py
│   └── main.py          # код приложения
├── requirements.txt     # зафиксированные версии зависимостей
├── Dockerfile.good      # хороший Dockerfile
├── Dockerfile.bad       # плохой Dockerfile
├── .dockerignore
└── README.md
```

## Сборка и запуск (хороший Dockerfile)

```bash
# сборка
docker build -f Dockerfile.good -t notes-api:good .

# создаём именованный volume и запускаем контейнер
docker volume create notes_data
docker run -d --name notes -p 8000:8000 -v notes_data:/app/data notes-api:good
```

Проверка:

```bash
curl -X POST localhost:8000/notes -H 'Content-Type: application/json' -d '{"text":"hello"}'
curl localhost:8000/notes
```

Проверка, что данные живут в volume, а не в контейнере:

```bash
docker rm -f notes
docker run -d --name notes -p 8000:8000 -v notes_data:/app/data notes-api:good
curl localhost:8000/notes   # заметка "hello" на месте
```

Состояние healthcheck:

```bash
docker inspect --format '{{.State.Health.Status}}' notes   # healthy
```

> **Bind mount вместо volume.** Приложение работает от пользователя с
> UID 10001, поэтому при монтировании папки хоста её нужно сделать доступной
> для записи: `mkdir -p data && sudo chown 10001:10001 data`, затем
> `docker run ... -v "$(pwd)/data:/app/data" notes-api:good`.

## Сборка и запуск (плохой Dockerfile)

<!-- TODO (Яхья): команды сборки и запуска Dockerfile.bad с volume, скриншоты -->

## Плохие практики в Dockerfile.bad и их исправление

<!-- TODO (Яхья): для каждой плохой практики — что это и почему плохо.
     Колонку «Как исправлено» заполним по Dockerfile.good. -->

| # | Плохая практика | Почему это плохо | Как исправлено в Dockerfile.good |
|---|-----------------|------------------|----------------------------------|
| 1 |                 |                  |                                  |
| 2 |                 |                  |                                  |
| 3 |                 |                  |                                  |

### Что сделано в Dockerfile.good

- **Фиксированная версия slim-образа** (`python:3.12.8-slim-bookworm`) вместо
  `latest`: сборка воспроизводима, образ меньше и содержит меньше уязвимостей.
- **Multi-stage build**: зависимости ставятся в stage `builder`, в финальный
  образ копируется только готовый venv — без pip-кэша и лишних инструментов.
- **Правильный порядок слоёв**: сначала копируется `requirements.txt` и ставятся
  зависимости, и только потом код. При изменении кода слой с зависимостями
  берётся из кэша, и пересборка занимает секунды.
- **Зафиксированные версии зависимостей** в `requirements.txt`.
- **`.dockerignore`**: в контекст сборки и образ не попадают `.git`, локальные
  данные, кэш Python, документация.
- **Непривилегированный пользователь** (`USER app`, UID 10001): при уязвимости
  в приложении злоумышленник не получает root в контейнере. Код принадлежит
  root и доступен приложению только на чтение, писать можно только в `/app/data`.
- **Без кэша pip** (`PIP_NO_CACHE_DIR=1`) и без лишних системных пакетов.
- **`HEALTHCHECK`**: Docker сам отслеживает, жив ли сервис.
- **exec-форма `CMD`**: uvicorn работает как PID 1 и корректно получает
  `SIGTERM` при `docker stop`, а не убивается через 10 секунд по `SIGKILL`.
- **`PYTHONUNBUFFERED=1`**: логи сразу попадают в `docker logs`.
- **Данные вынесены в volume** (`/app/data`), путь задаётся через `DATA_DIR`.

## Плохие практики при использовании контейнера

<!-- TODO (Яхья): две плохие практики использования этого контейнера -->

1.
2.

## Когда НЕ стоит использовать контейнеры

<!-- TODO (Яхья): два случая -->

1.
2.
