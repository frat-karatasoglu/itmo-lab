# Notes API — лабораторные по контейнеризации (ITMO)

**Команда:** Firat Karatasoglu, Yahya

| ЛР | Тема | Раздел |
|----|------|--------|
| 1 | Dockerfile | [ЛР 1. Dockerfile](#лр-1-dockerfile) |
| 2 | Docker Compose | [ЛР 2. Docker Compose](#лр-2-docker-compose) |
| 3 | Kubernetes | [ЛР 3. Kubernetes](#лр-3-kubernetes) |

История изменений — в [CHANGES.md](CHANGES.md).

## Приложение

**Notes API** — небольшой REST-сервис заметок на FastAPI. Хранилище
выбирается переменными окружения:

- **без `DB_HOST`** (ЛР 1) — SQLite-файл в каталоге `/app/data`, который
  монтируется как **volume**;
- **с `DB_HOST`** (ЛР 2) — PostgreSQL в отдельном контейнере, схему БД
  создаёт одноразовый init-сервис.

Эндпоинт `/health` используется в healthcheck и пригодится для
liveness/readiness probe в Kubernetes.

| Метод    | Путь           | Описание                     |
|----------|----------------|------------------------------|
| `GET`    | `/`            | Информация о сервисе и типе хранилища |
| `GET`    | `/health`      | Проверка состояния (в том числе БД) |
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
│   ├── main.py          # HTTP API
│   ├── db.py            # доступ к БД: SQLite или PostgreSQL
│   └── migrate.py       # создание схемы БД (init-сервис в ЛР 2)
├── requirements.txt     # зафиксированные версии зависимостей
├── Dockerfile.good      # хороший Dockerfile (ЛР 1, используется в ЛР 2)
├── Dockerfile.bad       # плохой Dockerfile (ЛР 1)
├── docker-compose.yml   # ЛР 2
├── .env                 # переменные окружения для docker compose (ЛР 2)
├── k8s/                 # манифесты Kubernetes (ЛР 3)
├── .dockerignore
├── screenshots/
├── CHANGES.md
└── README.md
```

---

# ЛР 1. Dockerfile

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

```bash
docker build -f Dockerfile.bad -t notes-api:bad .
docker volume create notes_data_bad
docker run -d --name notes-bad -p 8001:8000 -v notes_data_bad:/app/data notes-api:bad
```

После запуска откройте Swagger UI по адресу http://localhost:8001/docs.
Порт 8001 позволяет одновременно держать запущенным хороший образ на порту 8000.

```bash
curl --fail-with-body http://localhost:8001/health
curl --fail-with-body -X POST http://localhost:8001/notes \
  -H 'Content-Type: application/json' -d '{"text":"Проверка volume"}'
curl --fail-with-body http://localhost:8001/notes

docker rm -f notes-bad
docker run -d --name notes-bad -p 8001:8000 -v notes_data_bad:/app/data notes-api:bad
curl --fail-with-body http://localhost:8001/notes
```

Последний запрос возвращает ту же заметку из именованного тома. Если
приложение ещё запускается, дождитесь успешного ответа от `/health`.
Для просмотра логов и сравнения размеров образов:

```bash
docker logs notes-bad
docker image ls notes-api
```

### Результаты локальной проверки

Оба образа собраны в Docker Desktop (Linux, amd64). Для каждого образа
`POST /notes` вернул HTTP 201, а `GET /notes` после пересоздания контейнера
с тем же именованным томом вернул ту же заметку и время её создания.
У `notes-api:good` Docker также показал статус `healthy`.

| Образ | Размер на диске | Размер содержимого |
|-------|-----------------|---------------------|
| `notes-api:good` | 226 МБ | 54,5 МБ |
| `notes-api:bad` | 1,79 ГБ | 467 МБ |

По выводу `docker image ls notes-api` плохой образ занял примерно в 7,9 раза
больше места на диске.

![Фрагменты логов успешной сборки обоих образов](screenshots/docker-builds.png)

![Ответы API до и после пересоздания контейнера, логи uvicorn](screenshots/volume-and-logs.png)

![Swagger UI работающего контейнера notes-api:bad](screenshots/swagger-ui.png)

![Вывод docker image ls с размерами обоих образов](screenshots/image-sizes.png)

## Плохие практики в Dockerfile.bad и их исправление

| # | Плохая практика | Почему это плохо | Как исправлено в Dockerfile.good |
|---|-----------------|------------------|----------------------------------|
| 1 | Полный образ `python:latest` | Тег меняется со временем. Следующая сборка может получить новую версию Python. Полный образ содержит больше системных пакетов. | Указана конкретная версия `python:3.12.8-slim-bookworm` для обоих этапов. |
| 2 | `apt-get update` и установка пакетов в разных слоях | При изменении списка пакетов Docker может переиспользовать слой с устаревшими индексами. Очистка в позднем слое не уменьшила бы размер раннего слоя. | Базового slim-образа хватает, поэтому вызовов APT и сохранённых индексов нет. |
| 3 | Установка `vim`, `nano` и `curl`, сохранение кэшей APT и pip | Редакторы, сетевой клиент и кэши увеличивают размер образа. Сервису они не нужны. | Лишние пакеты не ставятся, pip работает с `PIP_NO_CACHE_DIR=1`, в финальный образ переносится готовый venv. |
| 4 | `COPY . .` до установки зависимостей | Изменение любого файла, попавшего в контекст, сбрасывает кэш слоя установки. Копирование всего контекста также приносит файлы, которые могут быть лишними при запуске. | Сначала копируется `requirements.txt` и ставятся зависимости. В финальный образ отдельно копируются venv и `app/`. |
| 5 | Запуск с унаследованным пользователем root | У процесса больше прав внутри контейнера. При уязвимости приложения расширяется набор доступных атакующему действий. | `USER app` задаёт UID 10001. Пользователю приложения принадлежит каталог данных. |
| 6 | Shell-форма `CMD` | Процесс `/bin/sh` занимает PID 1 и может не передать сигнал остановки uvicorn. | Exec-форма `CMD` запускает uvicorn напрямую, поэтому сервер получает `SIGTERM`. |
| 7 | Нет `HEALTHCHECK` | Docker видит запущенный процесс, даже если HTTP-сервис перестал отвечать. | `HEALTHCHECK` периодически проверяет `/health` и отражает результат в статусе контейнера. |

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

1. **Хранить SQLite в слое контейнера.** Если запустить Notes API без тома
   на `/app/data`, при удалении контейнера исчезнет и база заметок. Подключайте
   именованный том и сохраняйте его при пересоздании контейнера.
2. **Монтировать сокет Docker в контейнер.** Notes API работает с SQLite
   и не управляет другими контейнерами. Доступ к `/var/run/docker.sock`
   даёт процессу возможность обращаться к демону Docker и управлять хостом.

## Когда НЕ стоит использовать контейнеры

1. **Нужно другое ядро ОС.** Например, для тестирования драйвера Windows
   на хосте Linux нужна виртуальная машина с ядром Windows. Обычный Linux-контейнер
   использует ядро Linux.
2. **Нужны гарантированные жёсткие сроки реакции.** Например, для аварийного
   отключения промышленной установки используют выделенный контроллер с ОС
   реального времени. Обычный Docker-контейнер на ОС общего назначения
   разделяет планировщик с другими процессами, поэтому сам по себе таких гарантий не даёт.

---

# ЛР 2. Docker Compose

Compose-проект из трёх сервисов на основе `Dockerfile.good` из ЛР 1:

| Сервис | Контейнер | Роль |
|--------|-----------|------|
| `db` | `notes-db` | PostgreSQL 16, данные в именованном volume `notes-pgdata` |
| `migrate` | `notes-migrate` | **init-сервис**: один раз создаёт схему БД и завершается с кодом 0 |
| `app` | `notes-api` | Notes API, порт 8000 проброшен наружу |

Порядок запуска: `db` становится `healthy` → `migrate` отрабатывает и
завершается → стартует `app`.

## Запуск

```bash
docker compose up -d --build
docker compose ps -a
```

Ожидаемый результат:

```
NAME            IMAGE                  STATUS                      PORTS
notes-api       notes-api:2.0.0        Up 20 seconds (healthy)     0.0.0.0:8000->8000/tcp
notes-db        postgres:16.6-alpine   Up 30 seconds (healthy)     5432/tcp
notes-migrate   notes-api:2.0.0        Exited (0) 20 seconds ago
```

Проверка:

```bash
docker logs notes-migrate
# [migrate] backend: postgres
# [migrate] schema is up to date, notes in table: 0

curl localhost:8000/
# {"service":"notes-api","version":"2.0.0","storage":"postgres","docs":"/docs"}

curl -X POST localhost:8000/notes -H 'Content-Type: application/json' -d '{"text":"compose + postgres"}'
curl localhost:8000/notes
```

Данные хранятся в volume, поэтому переживают `docker compose down`:

```bash
docker compose down
docker compose up -d
curl localhost:8000/notes   # заметка на месте
```

Полная очистка вместе с данными: `docker compose down -v`.

> Файл `.env` лежит в репозитории, потому что этого требует задание.
> В реальном проекте в git хранят только `.env.example` с примерами значений,
> а настоящий `.env` добавляют в `.gitignore`. В образ `.env` не попадает:
> он указан в `.dockerignore`.

### Результаты локальной проверки

Compose-проект собран и запущен на Windows 11 (Docker Desktop, Linux-контейнеры,
Docker Engine 29.8.2). Результат: `notes-db` и `notes-api` — `healthy`,
`notes-migrate` — `Exited (0)`. `POST /notes` вернул HTTP 201, `GET /notes` —
созданную заметку. Заметка, созданная до `docker compose down`, осталась в
именованном томе `notes-pgdata` и видна после повторного `docker compose up`
(в выводе `GET /notes` на скриншоте видны обе заметки, а `migrate` сообщает
`notes in table: 1` — схема уже была создана ранее).

![Вывод docker compose up -d --build: сборка образа notes-api:2.0.0 и запуск трёх сервисов](screenshots/lab2-compose-up.png)

![docker compose ps -a, логи notes-migrate, POST/GET /notes и лимиты ресурсов notes-api](screenshots/lab2-compose-ps.png)

![Swagger UI приложения на http://localhost:8000/docs](screenshots/lab2-docs.png)

## Описание docker-compose.yml

Верхнеуровневый ключ `name: notes` задаёт имя проекта. Оно подставляется в имена
создаваемых объектов и позволяет не зависеть от имени каталога, в котором лежит
`docker-compose.yml`.

### Якорь `x-notes-image`

```yaml
x-notes-image: &notes-image
  build:
    context: .
    dockerfile: Dockerfile.good
  image: notes-api:2.0.0
  env_file: .env
  networks:
    - notes-net
```

Ключи верхнего уровня, которые начинаются с `x-`, — это *extension fields*.
Compose их не считает сервисами и не пытается запускать, поэтому в них удобно
хранить общий кусок конфигурации.

`&notes-image` — это **якорь** YAML, а `<<: *notes-image` в сервисах `migrate` и
`app` — **слияние** (merge) этого блока в сервис. Так общие настройки записаны
один раз, а не продублированы дважды: оба сервиса собираются из одного и того же
`Dockerfile.good`, получают один и тот же тег образа `notes-api:2.0.0`, один и
тот же `.env` и одну и ту же сеть. Образ при этом собирается **один раз**:
второй сервис видит, что образ с таким тегом уже собран, и переиспользует его.
Если якорь понадобится переопределить, достаточно дописать нужный ключ прямо в
сервисе — значение из сервиса побеждает значение из якоря.

### Сервис `db` — PostgreSQL

| Ключ | Значение и зачем он нужен |
|------|---------------------------|
| `image: postgres:16.6-alpine` | Готовый официальный образ. Тег зафиксирован до патч-версии, а не `latest`, поэтому сборка воспроизводима. Вариант `alpine` меньше по размеру. |
| `container_name: notes-db` | Фиксированное имя контейнера вместо автогенерируемого `notes-db-1`. Удобно для `docker logs notes-db`, `docker exec -it notes-db psql`. Обратная сторона: имя должно быть уникальным на хосте и сервис нельзя масштабировать через `--scale`. |
| `env_file: .env` | Переменные берутся из файла, а не хардкодятся в YAML. Отсюда образ `postgres` получает `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` и при первом запуске создаёт базу и пользователя. |
| `volumes: - pgdata:/var/lib/postgresql/data` | Каталог с данными PostgreSQL вынесен в **именованный том**. Контейнер можно удалить и пересоздать — данные останутся. |
| `networks: - notes-net` | Сервис подключён к нашей пользовательской сети. |
| `healthcheck` | `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` раз в 5 с, таймаут 3 с, 10 попыток, `start_period: 10s` (первые 10 с неудачи не считаются). Пока проверка не прошла, статус контейнера — `health: starting`, потом `healthy`. Именно на этот статус опираются `depends_on` у `migrate` и `app`. Двойной знак `$$` нужен, чтобы Compose **не** подставлял переменную сам, а передал строку `$POSTGRES_USER` внутрь контейнера — там её раскроет shell. |
| `restart: unless-stopped` | Контейнер перезапускается при падении и после перезагрузки демона, но остаётся остановленным, если его остановили вручную. |

Порт `5432` наружу **не публикуется**: база доступна только внутри сети
`notes-net`. Это сознательное решение — наружу торчит только API.

### Сервис `migrate` — одноразовый init-сервис

| Ключ | Значение и зачем он нужен |
|------|---------------------------|
| `<<: *notes-image` | Подставляет `build`, `image`, `env_file`, `networks` из якоря. |
| `build.context: .` + `build.dockerfile: Dockerfile.good` | Образ собирается из исходников репозитория «хорошим» Dockerfile из ЛР 1 (multi-stage, непривилегированный пользователь, exec-форма CMD). |
| `image: notes-api:2.0.0` | Имя и тег, под которым сохраняется собранный образ. Если образ с таким тегом уже есть, Compose не собирает его заново без `--build`. |
| `container_name: notes-migrate` | Предсказуемое имя для `docker logs notes-migrate`. |
| `command: ["python", "-m", "app.migrate"]` | Переопределяет `CMD` из образа: вместо uvicorn запускается миграция. Exec-форма (список), поэтому процесс получает PID 1 и корректно принимает сигналы. |
| `depends_on: db: condition: service_healthy` | Миграция стартует только после того, как база **готова принимать соединения**, а не просто «контейнер запущен». |
| `healthcheck: disable: true` | Отключает `HEALTHCHECK`, унаследованный из `Dockerfile.good`. Он проверяет HTTP-эндпоинт `/health`, которого у миграции нет, и контейнер, который сразу завершается, всё равно считался бы `unhealthy`. |
| `restart: "no"` | Обязательно для init-сервиса: иначе Docker бесконечно перезапускал бы контейнер, который нормально завершился с кодом 0. |

После успешной работы контейнер остаётся в состоянии `Exited (0)` — это и есть
признак, которого ждёт сервис `app`.

### Сервис `app` — Notes API

| Ключ | Значение и зачем он нужен |
|------|---------------------------|
| `<<: *notes-image` | Те же `build`, `image`, `env_file`, `networks`. Образ уже собран сервисом `migrate`, поэтому повторной сборки не происходит. |
| `container_name: notes-api` | Фиксированное имя контейнера. |
| `command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]` | Явно повторяет `CMD` образа. Важно `--host 0.0.0.0`: иначе uvicorn слушал бы только loopback внутри контейнера и проброс порта не работал бы. |
| `ports: - "${APP_PORT}:8000"` | Публикация порта наружу: слева порт хоста (из `.env`, по умолчанию 8000), справа порт внутри контейнера. Только у этого сервиса есть доступ снаружи. |
| `depends_on: db: service_healthy` | API не стартует, пока база не `healthy`. |
| `depends_on: migrate: service_completed_successfully` | API не стартует, пока миграция не завершится **успешно** (код выхода 0). Если миграция упадёт, `app` не запустится вообще — это защищает от работы приложения на несозданной схеме. |
| `healthcheck` | HTTP-проверка `/health` средствами самого Python (`urllib.request`) раз в 15 с. Внешние утилиты вроде `curl` в «хорошем» образе не ставятся, поэтому проверка написана на том, что уже есть. |
| `deploy.resources.limits` | Жёсткие лимиты: `cpus: "0.50"` и `memory: 256M`. Подробнее — в ответе на вопрос ниже. |
| `restart: unless-stopped` | Автоперезапуск API при падении. |

#### Разница условий в `depends_on`

| Условие | Когда зависимый сервис начинает запускаться |
|---------|---------------------------------------------|
| `service_started` | Сразу после того, как контейнер зависимости **запущен**. Это поведение по умолчанию для короткой формы `depends_on: [db]`. Готовность процесса внутри контейнера не проверяется. |
| `service_healthy` | Когда `healthcheck` зависимости впервые вернул `healthy`. Используем для `db`. |
| `service_completed_successfully` | Когда контейнер зависимости **завершился** с кодом выхода 0. Используем для `migrate`. |

Без `service_healthy` приложение почти наверняка упало бы на старте: контейнер
PostgreSQL поднимается за доли секунды, а сам сервер готов принимать соединения
на несколько секунд позже.

### `networks`

```yaml
networks:
  notes-net:
    name: notes-net
    driver: bridge
```

Своя пользовательская bridge-сеть. Внутри неё работает встроенный DNS Docker:
контейнеры видят друг друга **по именам сервисов**, поэтому в `.env` указано
`DB_HOST=db`, а не IP-адрес. Ключ `name` задаёт точное имя сети — без него
Compose назвал бы её `notes_notes-net`. Если бы блока `networks` не было вовсе,
Compose всё равно создал бы сеть `notes_default`; здесь она объявлена явно, чтобы
имя было предсказуемым.

### `volumes`

```yaml
volumes:
  pgdata:
    name: notes-pgdata
```

Объявление именованного тома, который монтируется в `db`. Данными управляет сам
Docker (на Windows том лежит внутри ВМ Docker Desktop), поэтому прав доступа к
хостовой файловой системе касаться не нужно. Том переживает `docker compose down`
и удаляется только явной командой `docker compose down -v`.

## Ответы на вопросы

### Можно ли ограничивать ресурсы (память, CPU) для сервисов в docker-compose.yml?

Да, можно. Актуальный способ — секция `deploy.resources`:

```yaml
deploy:
  resources:
    limits:        # жёсткий потолок
      cpus: "0.50"
      memory: 256M
    reservations:  # мягкая «бронь» ресурсов
      cpus: "0.10"
      memory: 64M
```

`limits` — это верхняя граница, которую контейнер не сможет превысить:
`cpus: "0.50"` означает половину ядра, `memory: 256M` — 256 МиБ ОЗУ (при
превышении процесс убивает OOM-killer). `reservations` — наоборот, нижняя
граница: сколько ресурсов планировщик обязан оставить сервису.

Важная деталь: исторически блок `deploy` относился к Docker Swarm, и старый
`docker-compose` v1 его игнорировал. В Docker Compose v2 (`docker compose`,
которым мы и пользуемся) `deploy.resources.limits` применяется и при обычном
`up`. Старые ключи-аналоги тоже поддерживаются: `mem_limit`, `cpus`,
`memswap_limit`, `pids_limit`.

В нашем файле лимиты заданы сервису `app`. Проверяем, что они действительно
применились к контейнеру:

```powershell
docker inspect notes-api --format "NanoCpus={{.HostConfig.NanoCpus}}  Memory={{.HostConfig.Memory}}"
# NanoCpus=500000000  Memory=268435456
```

`500000000` нано-CPU = 0,5 ядра, `268435456` байт = 256 МиБ — ровно то, что
записано в `docker-compose.yml`. То же видно и в `docker stats`:

```powershell
docker stats notes-api --no-stream --format "{{.Name}} CPU={{.CPUPerc}} MEM={{.MemUsage}} ({{.MemPerc}})"
# notes-api CPU=0.14% MEM=43.02MiB / 256MiB (16.81%)
```

Знаменатель `256MiB` — это и есть лимит, а не объём памяти хоста. Вывод
`docker inspect` виден и на скриншоте
[`lab2-compose-ps.png`](screenshots/lab2-compose-ps.png).

### Как запустить только определённый сервис из docker-compose.yml?

Достаточно указать имя сервиса в команде:

```bash
docker compose up -d db
```

По умолчанию Compose поднимет не только сам сервис, но и всё, от чего он зависит
по `depends_on`. Чтобы запустить сервис **без зависимостей**, добавляется
`--no-deps`:

```bash
docker compose up -d --no-deps app
```

Другие полезные варианты:

| Команда | Что делает |
|---------|------------|
| `docker compose up -d db` | Поднимает сервис вместе с его зависимостями. |
| `docker compose up -d --no-deps app` | Поднимает только указанный сервис. Удобно, когда БД уже работает и нужно перевыкатить одно приложение (`--build` пересоберёт только его образ). |
| `docker compose run --rm [--no-deps] app <команда>` | Разовый запуск команды в новом контейнере сервиса. Порты из `ports` при этом не публикуются, а `--rm` удаляет контейнер после выхода. |
| `docker compose stop app` / `docker compose start app` | Остановить/запустить один уже созданный контейнер. |
| `profiles: ["debug"]` у сервиса | Сервис не запускается при обычном `up` и поднимается только с `--profile debug`. Так исключают из обычного запуска отладочные и вспомогательные сервисы. |

Проверено на нашем проекте — поднимаем только базу:

```powershell
PS C:\Masaüstü\itmo-lab> docker compose up -d --no-deps db
 Network notes-net  Created
 Container notes-db  Created
 Container notes-db  Started

PS C:\Masaüstü\itmo-lab> docker compose ps -a
NAME       IMAGE                  COMMAND                  SERVICE   CREATED        STATUS                                     PORTS
notes-db   postgres:16.6-alpine   "docker-entrypoint.s…"   db        1 second ago   Up Less than a second (health: starting)   5432/tcp
```

Контейнеров `notes-migrate` и `notes-api` в списке нет — запустился ровно один
сервис. И разовая команда в контейнере приложения, тоже без зависимостей:

```powershell
PS C:\Masaüstü\itmo-lab> docker compose run --rm --no-deps app python -c "print('one-off command, no app container started')"
 Container notes-app-run-58ab7ff11cc3  Created
one-off command, no app container started
```

---

# ЛР 3. Kubernetes

В кластере minikube разворачивается Nextcloud с БД PostgreSQL. За основу
взяты манифесты из задания. В них внесены изменения, которых требует задание,
и несколько исправлений, без которых пример работает нестабильно.

## Манифесты (`k8s/`)

| Файл | Объекты | Назначение |
|------|---------|------------|
| `pg_configmap.yml` | ConfigMap `postgres-configmap` | `POSTGRES_DB` |
| `pg_secret.yml` | Secret `postgres-secret` | `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| `pg_service.yml` | Service `postgres-service` (ClusterIP) | адрес БД внутри кластера |
| `pg_deployment.yml` | Deployment `postgres` | PostgreSQL 14 |
| `nextcloud.yml` | Secret `nextcloud-secret`, ConfigMap `nextcloud-configmap`, Deployment `nextcloud` | Nextcloud с пробами |
| `nextcloud_service.yml` | Service `nextcloud` (NodePort) | доступ к Nextcloud снаружи |

## Что изменено по заданию

1. **PostgreSQL: логин и пароль перенесены из ConfigMap в Secret.**
   В `postgres-configmap` остался только `POSTGRES_DB`. `POSTGRES_USER` и
   `POSTGRES_PASSWORD` лежат в новом `postgres-secret`. Postgres получает
   обе сущности через `envFrom` (`configMapRef` + `secretRef`), а Nextcloud
   берёт логин и пароль БД из того же секрета через `secretKeyRef`.
2. **Nextcloud: переменные перенесены из Deployment в ConfigMap.**
   `NEXTCLOUD_UPDATE`, `ALLOW_EMPTY_PASSWORD`, `POSTGRES_HOST`,
   `NEXTCLOUD_TRUSTED_DOMAINS` и `NEXTCLOUD_ADMIN_USER` теперь находятся в
   `nextcloud-configmap` и подключаются через `envFrom`. В `env` Deployment'а
   остались только ссылки на чужие ConfigMap/Secret: `POSTGRES_DB`,
   `POSTGRES_USER`, `POSTGRES_PASSWORD`, `NEXTCLOUD_ADMIN_PASSWORD`.
3. **Nextcloud: добавлены пробы.** Все три проверяют `GET /status.php`:

   | Проба | Что делает | Параметры |
   |-------|-----------|-----------|
   | `startupProbe` | Ждёт окончания первой установки Nextcloud. Пока она не прошла, остальные пробы не запускаются | раз в 10 с, до 60 неудач (10 минут) |
   | `livenessProbe` | Если Apache перестал отвечать, kubelet перезапускает контейнер | раз в 15 с, 3 неудачи подряд |
   | `readinessProbe` | Пока проба не проходит, под исключается из Endpoints сервиса и не получает трафик | раз в 10 с, 3 неудачи подряд |

   `startupProbe` нужна потому, что первая установка Nextcloud длится
   несколько минут, и всё это время Apache не слушает порт 80. С одной только
   `livenessProbe` kubelet перезапускал бы контейнер посреди установки, и под
   ушёл бы в `CrashLoopBackOff`.

   Пробы отправляют заголовок `Host: localhost`. Nextcloud может отвечать
   ошибкой на запросы с недоверенным доменом, а kubelet по умолчанию подставляет IP
   пода, поэтому `localhost` добавлен в `NEXTCLOUD_TRUSTED_DOMAINS`.

### Дополнительные исправления примера

- **Service БД — `ClusterIP` вместо `NodePort`.** Базе данных не нужен доступ
  снаружи кластера, Nextcloud обращается к ней по имени `postgres-service`.
- **Лимит памяти Nextcloud поднят с 256Mi до 768Mi.** 256Mi впритык для первой
  установки Nextcloud, и контейнер может быть убит по OOM (`OOMKilled`).
- **`NEXTCLOUD_TRUSTED_DOMAINS`** содержит `localhost` (для проб), `127.0.0.1`
  (`minikube service` с драйвером docker на Windows/macOS) и `192.168.49.2`
  (IP ноды minikube по умолчанию, проверить: `minikube ip`).
- **Service Nextcloud описан манифестом** `nextcloud_service.yml`, поэтому
  `kubectl expose` не нужен. Используйте что-то одно: оба способа создают
  сервис с именем `nextcloud`.
- Пароли в секретах — заглушки `change_me_*`. Перед запуском их стоит заменить.

## Запуск

```bash
minikube start
kubectl config current-context        # minikube

kubectl create -f k8s/pg_configmap.yml
kubectl create -f k8s/pg_secret.yml
kubectl create -f k8s/pg_service.yml
kubectl create -f k8s/pg_deployment.yml
kubectl create -f k8s/nextcloud.yml
kubectl create -f k8s/nextcloud_service.yml
# или всё сразу: kubectl apply -f k8s/

kubectl get pods -w                    # ждём 1/1 Running у обоих подов
kubectl logs deployment/nextcloud -f   # ждём "Nextcloud was successfully installed"
minikube service nextcloud             # откроет Nextcloud в браузере
```

Логин — `admin`, пароль — значение `NEXTCLOUD_ADMIN_PASSWORD` из `nextcloud-secret`.

Удаление: `kubectl delete -f k8s/`.

## Ход работы

Проверка выполнена на Windows 11 (Docker Desktop, Docker Engine 29.8.2),
minikube v1.39.0, драйвер `docker`, Kubernetes v1.37.0, `kubectl` v1.36.1.
Ниже — реальный вывод команд.

### 1. Запуск кластера

```powershell
minikube start --driver=docker
kubectl config current-context
kubectl get nodes
```

```
* minikube v1.39.0 on Microsoft Windows 11 Pro 26H2
* Using the docker driver based on user configuration
* Starting "minikube" primary control-plane node in "minikube" cluster
* Pulling base image v0.0.51 ...
* Preparing Kubernetes v1.37.0 on containerd 2.3.4 ...
* Configuring CNI (Container Networking Interface) ...
* Verifying Kubernetes components...
* Enabled addons: storage-provisioner, default-storageclass
* Done! kubectl is now configured to use "minikube" cluster
```

Сам кластер — это контейнер в Docker: `docker ps` показывает контейнер
`minikube` с образом `gcr.io/k8s-minikube/kicbase`. Состояние поднятого
кластера (`minikube status`, текущий контекст, `kubectl get nodes`) видно на
скриншоте в следующем разделе.

### 2. Создание манифестов по порядку

Порядок важен (см. вопрос 1): сначала ConfigMap и Secret, затем Service и
Deployment базы, и только потом Nextcloud.

```powershell
kubectl create -f k8s/pg_configmap.yml
kubectl create -f k8s/pg_secret.yml
kubectl create -f k8s/pg_service.yml
kubectl create -f k8s/pg_deployment.yml
kubectl create -f k8s/nextcloud.yml
kubectl create -f k8s/nextcloud_service.yml
```

```
configmap/postgres-configmap created
secret/postgres-secret created
service/postgres-service created
deployment.apps/postgres created
secret/nextcloud-secret created
configmap/nextcloud-configmap created
deployment.apps/nextcloud created
service/nextcloud created
```

Все объекты созданы без ошибок `configmap "..." not found`, потому что
ConfigMap и Secret появились раньше Deployment'ов.

### 3. Проверка созданных объектов

```powershell
kubectl get configmap,secret,service
```

```
NAME                            DATA   AGE
configmap/kube-root-ca.crt      1      4h35m
configmap/nextcloud-configmap   5      0s
configmap/postgres-configmap    1      1s

NAME                      TYPE     DATA   AGE
secret/nextcloud-secret   Opaque   1      0s
secret/postgres-secret    Opaque   2      1s

NAME                       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
service/kubernetes         ClusterIP   10.96.0.1       <none>        443/TCP        4h35m
service/nextcloud          NodePort    10.106.45.95    <none>        80:32556/TCP   0s
service/postgres-service   ClusterIP   10.99.71.82     <none>        5432/TCP       1s
```

Видно, что `postgres-service` — `ClusterIP` (наружу не публикуется), а
`nextcloud` — `NodePort` с портом ноды `32556`.

![minikube status, текущий контекст, создание манифестов и список объектов](screenshots/lab3-create.png)

### 4. Секрет: значения не показываются

```powershell
kubectl describe secret postgres-secret
```

```
Name:         postgres-secret
Namespace:    default
Labels:       app=postgres
Annotations:  <none>

Type:  Opaque

Data
====
POSTGRES_PASSWORD:  21 bytes
POSTGRES_USER:      9 bytes
```

`describe` выводит только имена ключей и размер значений. Это не шифрование:
в etcd Secret хранится в base64, и значение при необходимости достаётся
командой `kubectl get secret postgres-secret -o jsonpath='{.data.POSTGRES_USER}'`
с последующим декодированием base64. Смысл Secret в другом: значение не видно
в манифесте Deployment, не попадает в `describe` и права на него выдаются
отдельно через RBAC.

![kubectl get pods, describe secret postgres-secret и лог Nextcloud](screenshots/lab3-pods.png)

### 5. Пробы Nextcloud

```powershell
kubectl describe pod -l app=nextcloud
```

```
Image:      docker.io/nextcloud:stable-apache
Limits:       cpu: 1        memory: 768Mi
Requests:     cpu: 250m     memory: 256Mi

Liveness:   http-get http://:http/status.php delay=0s timeout=5s period=15s #success=1 #failure=3
Readiness:  http-get http://:http/status.php delay=0s timeout=5s period=10s #success=1 #failure=3
Startup:    http-get http://:http/status.php delay=0s timeout=5s period=10s #success=1 #failure=60
```

Все три пробы применились. В событиях пода видно, зачем нужна `startupProbe`:

```
Warning  Unhealthy  73s  kubelet  pod/nextcloud-7bf984646f-z75mr
  Startup probe failed: Get "http://10.244.0.5:80/status.php":
  dial tcp 10.244.0.5:80: connect: connection refused
```

Пока Nextcloud разворачивался, проба получала `connection refused` — Apache
ещё не слушал порт 80. `startupProbe` допускает до 60 таких неудач подряд
(10 минут), поэтому контейнер не был перезапущен и дошёл до готовности. Если
бы вместо неё работала только `livenessProbe` (`failureThreshold: 3`,
`periodSeconds: 15`), kubelet убил бы контейнер примерно через 45 секунд и
под ушёл бы в `CrashLoopBackOff`.

![Пробы из describe pod, события с результатом startup-пробы и лог установки](screenshots/lab3-probes.png)

### 6. Поды и лог установки

```powershell
kubectl get pods -o wide
kubectl logs deployment/nextcloud
```

```
NAME                         READY   STATUS    RESTARTS   AGE   IP           NODE
nextcloud-7bf984646f-z75mr   1/1     Running   0          12m   10.244.0.5   minikube
postgres-848ffcb678-hnjwc    1/1     Running   0          12m   10.244.0.4   minikube

Initializing nextcloud 34.0.6.2 ...
New nextcloud instance
Nextcloud was successfully installed
Initializing finished
```

Оба пода `1/1 Running`, перезапусков нет. По времени (из событий): образ
`postgres:14` (163 МБ) скачивался 4 мин 25 с, образ
`nextcloud:stable-apache` (513 МБ) — 5 мин 43 с (10 мин 8 с вместе с
ожиданием в очереди), после старта контейнера установка заняла ещё около
двух минут.

### 7. Доступ к Nextcloud

```powershell
minikube service nextcloud --url
```

```
http://127.0.0.1:64559
! Because you are using a Docker driver on windows, the terminal needs to be open to run it.
```

С драйвером `docker` на Windows `minikube service` поднимает туннель на
`127.0.0.1` со случайным портом, и терминал с этой командой нужно оставить
открытым. Напрямую на `http://192.168.49.2:32556` с хоста зайти нельзя —
поэтому `127.0.0.1` и указан в `NEXTCLOUD_TRUSTED_DOMAINS`.

Страница входа и интерфейс после входа (логин `admin`, пароль — значение
`NEXTCLOUD_ADMIN_PASSWORD` из `nextcloud-secret`):

![Страница входа Nextcloud через minikube service](screenshots/lab3-nextcloud-login.png)

![Nextcloud после входа: приложение «Файлы» с данными по умолчанию](screenshots/lab3-nextcloud-files.png)

### 8. Эксперимент: `scale postgres` 0 → 1

```powershell
kubectl scale deployment postgres --replicas=0
kubectl get pods
kubectl scale deployment postgres --replicas=1
kubectl get pods
```

Сначала убеждаемся, что таблицы на месте:

```
                    List of relations
 Schema |            Name             | Type  |  Owner
--------+-----------------------------+-------+----------
 public | oc_accounts                 | table | oc_admin
 public | oc_accounts_data            | table | oc_admin
 public | oc_activity                 | table | oc_admin
```

Затем сам эксперимент:

```
deployment.apps/postgres scaled
NAME                         READY   STATUS    RESTARTS   AGE
nextcloud-7bf984646f-z75mr   1/1     Running   0          14m

deployment.apps/postgres scaled
NAME                         READY   STATUS    RESTARTS   AGE
nextcloud-7bf984646f-z75mr   1/1     Running   0          14m
postgres-848ffcb678-9srr9    1/1     Running   0          20s

--- таблицы в новом поде postgres ---
Did not find any relations.
```

Обратите внимание на имя пода: вместо `postgres-848ffcb678-hnjwc` появился
**новый** под `postgres-848ffcb678-9srr9`. Старый удалён вместе со своей
файловой системой, а с ней — и с каталогом `/var/lib/postgresql/data`.
База `nextcloud` создана заново и пуста: ни одной таблицы.
(`Did not find any relations.` psql пишет в stderr, поэтому PowerShell
подсвечивает строку красным.)

![Таблицы до эксперимента, scale 0 → 1 и пустая БД после него](screenshots/lab3-scale.png)

#### Что происходит с Nextcloud дальше

Под Nextcloud не пересоздавался, его `config.php` по-прежнему считает
установку выполненной, поэтому он обращается к несуществующим таблицам и
отдаёт HTTP 500:

![Nextcloud после scale postgres 0 → 1: Internal Server Error](screenshots/lab3-scale-error.png)

Дальше в дело вступают пробы, и это хорошо видно в кластере:

```
NAME                         READY   STATUS    RESTARTS      AGE
nextcloud-7bf984646f-z75mr   0/1     Running   1 (36s ago)   15m
postgres-848ffcb678-9srr9    1/1     Running   0             64s

NAME        ENDPOINTS   AGE
nextcloud               15m

Warning  Unhealthy  Readiness probe failed: HTTP probe failed with statuscode: 500
Warning  Unhealthy  Liveness probe failed: HTTP probe failed with statuscode: 500
```

1. `readinessProbe` получает 500 → под уходит из `Endpoints` сервиса
   (колонка `ENDPOINTS` пустая), и `minikube service nextcloud` начинает
   отдавать `ERR_CONNECTION_RESET`: трафик просто некуда направлять.
2. `livenessProbe` получает 500 три раза подряд → kubelet перезапускает
   контейнер (`RESTARTS 1`).
3. Перезапуск контейнера — это **новый контейнер из образа**, а не
   возобновление старого процесса. Файловая система контейнера при этом
   сбрасывается, и вместе с ней пропадает `config.php`, в котором стояло
   `installed => true`: своего тома у Nextcloud в этих манифестах тоже нет.
   Поэтому entrypoint образа видит пустую базу и чистый `/var/www/html` и
   **ставит Nextcloud заново**: в логе снова появляется `Nextcloud was
   successfully installed`, таблицы `oc_*` создаются с нуля, под опять
   становится `1/1`.

![Пробы после эксперимента: 500, пустые Endpoints и перезапуск контейнера](screenshots/lab3-scale-probes.png)

То есть сервис в итоге сам поднимается, но это **новая пустая установка**:
все прежние данные потеряны безвозвратно. Это ровно то, о чём ответ на
вопрос 2: без PersistentVolumeClaim и StatefulSet данные БД живут только
внутри пода и исчезают вместе с ним.

### 9. Удаление

```powershell
kubectl delete -f k8s/
minikube delete
```

## Ответы на вопросы

### 1. Важен ли порядок выполнения манифестов? Почему?

Отчасти важен.

- **ConfigMap и Secret нужно создать раньше Deployment, который на них
  ссылается.** Если Deployment создан первым, под не стартует и висит в
  статусе `CreateContainerConfigError` (`configmap "..." not found`). Когда
  ConfigMap/Secret появятся, kubelet сам повторит попытку и под запустится,
  так что ошибка не фатальная, но лучше её не допускать.
- **Порядок Service и Deployment не важен.** Service находит поды по label
  `selector` и обновляет Endpoints, когда поды появляются или исчезают.
  Единственное следствие: переменные окружения вида `POSTGRES_SERVICE_HOST`
  попадают только в поды, созданные после Service. Наши манифесты обращаются
  к сервису по DNS-имени (`postgres-service`), поэтому их это не касается.
- **Порядок БД и Nextcloud важен на практике.** Если Nextcloud стартует
  раньше, чем PostgreSQL готов принимать соединения, первая установка может
  завершиться ошибкой. Поэтому сначала создаётся БД, а Nextcloud — после
  того, как под `postgres` перешёл в `Running`.

`kubectl apply -f k8s/` применяет файлы каталога в алфавитном порядке. У нас
это `nextcloud.yml` → `nextcloud_service.yml` → `pg_configmap.yml` →
`pg_deployment.yml` → `pg_secret.yml` → `pg_service.yml`, то есть Nextcloud
создаётся раньше БД и её ConfigMap/Secret. Поды какое-то время побудут в
`CreateContainerConfigError`, а потом запустятся сами. Для предсказуемости в
инструкции выше файлы создаются по одному в правильном порядке.

### 2. Что произойдёт, если отскейлить postgres в 0, затем обратно в 1, и снова зайти в Nextcloud?

```bash
kubectl scale deployment postgres --replicas=0
kubectl scale deployment postgres --replicas=1
```

**Nextcloud перестанет работать** и покажет ошибку (`Internal Server Error`
или сообщение о проблемах с БД).

Причина в том, что у PostgreSQL **нет постоянного хранилища**: каталог
`/var/lib/postgresql/data` находится в файловой системе контейнера. При
`replicas=0` под удаляется вместе со всеми данными. При `replicas=1`
создаётся новый под с **пустой** БД: entrypoint образа postgres заново
создаёт пользователя и базу `nextcloud`, но без таблиц.

Nextcloud при этом продолжает работать в старом поде. Его `config.php`
говорит, что установка уже выполнена (`installed => true`), поэтому
переустановку он не запускает, а обращается к таблицам, которых больше нет.

Как исправить: хранить данные PostgreSQL в **PersistentVolumeClaim**,
смонтированном в `/var/lib/postgresql/data`, а для БД вместо Deployment
использовать **StatefulSet**. Тогда после scale 0 → 1 новый под подключит тот
же том и данные сохранятся.

