# DadeKavan-PD-X — Real-Time TSETMC Data Pipeline

A real-time market-data pipeline built with Python 3.11.2.

The system retrieves TSETMC order-book data for 10 stocks and ETFs at a target interval of 350 ms, publishes structured JSON to Redis, persists the data asynchronously to MySQL, provides human-readable access through Django, and exposes machine-readable data through FastAPI.

## Technology

- Python: **3.11.2**
- Environment manager: **Python `venv` + `pip`**
- Redis
- MySQL
- SQLAlchemy 2.x
- Django
- FastAPI
- Docker Compose

## Architecture

```text
TSETMC
  |
  v
WorkerA
  |
  +--> Redis Pub/Sub: DadeKavan-PD-X
  |
  +--> Redis Stream: DadeKavan-PD-X-stream
              |
              v
          WorkerB
              |
              v
          MySQL / RTDS
          /         \
         v           v
 Django :6280     FastAPI :6288
    /app             /api
```

WorkerA publishes each processed market-data message to the required Redis Pub/Sub channel. A Redis Stream is also used for reliable delivery to WorkerB. WorkerB stores each message in MySQL inside a transaction and acknowledges the Redis message only after the database commit succeeds.

## Configuration

Configuration is loaded from `.env`.

### Redis

```dotenv
REDIS_HOST=127.0.0.1
REDIS_PORT=6204
REDIS_PASSWORD='DadeKavan-PD-X-P@$$'
```

### MySQL

```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_PORT=6206
MYSQL_USER=DadeKavan-PD-X-USER
MYSQL_PASSWORD='DadeKavan-PD-X-P@$$'
MYSQL_DATABASE=DadeKavan-PD-X
```

The static FastAPI API key is also defined in `.env` and is sent through the `X-API-Key` request header.

## Run with Docker

Start the full stack:

```bash
docker compose up --build -d
```

Check service status:

```bash
docker compose ps
```

Create a Django administrator if needed:

```bash
docker compose exec django python django_app/manage.py createsuperuser
```

Useful URLs:

- Django: `http://127.0.0.1:6280/app/`
- Django login: `http://127.0.0.1:6280/app/login/`
- Django profile: `http://127.0.0.1:6280/app/profile/`
- Django admin: `http://127.0.0.1:6280/app/admin/`
- FastAPI Swagger: `http://127.0.0.1:6288/api/docs`

View worker logs:

```bash
docker compose logs -f worker-a worker-b
```

## Local setup without Docker

Create and activate a Python 3.11.2 virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run Redis locally on `127.0.0.1:6204` with the required password:

```bash
redis-server --port 6204 --requirepass 'DadeKavan-PD-X-P@$$'
```

Run MySQL on port `6206`, then create the required database and user:

```sql
CREATE DATABASE `DadeKavan-PD-X`
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER 'DadeKavan-PD-X-USER'@'localhost'
IDENTIFIED BY 'DadeKavan-PD-X-P@$$';

GRANT ALL PRIVILEGES
ON `DadeKavan-PD-X`.*
TO 'DadeKavan-PD-X-USER'@'localhost';

FLUSH PRIVILEGES;
```

Run Django migrations:

```bash
python django_app/manage.py migrate
```

Start each process in a separate terminal:

```bash
python -m workers.worker_a
python -m workers.worker_b
python django_app/manage.py runserver 0.0.0.0:6280
uvicorn fastapi_app.main:app --host 0.0.0.0 --port 6288
```

## WorkerA

`workers/worker_a.py` retrieves order-book data from TSETMC for 10 configured instruments.

Configured assets:

- فملی
- فولاد
- خودرو
- وبملت
- شپنا
- شبندر
- شستا
- کگل
- دارا یکم
- پالایش

WorkerA:

- resolves each symbol to its TSETMC `insCode`
- retrieves `BestLimits/{insCode}`
- performs requests asynchronously
- processes the order-book response into a consistent structure
- targets a 350 ms polling interval
- publishes JSON to Redis channel `DadeKavan-PD-X`
- also writes the same message to a Redis Stream for reliable WorkerB processing

Example message:

```json
{
  "schemaVersion": 1,
  "source": "TSETMC",
  "instrumentId": "35425587644337450",
  "symbol": "فملی",
  "assetType": "stock",
  "observedAt": "2026-09-21T16:29:36.148958Z",
  "exchangeTime": null,
  "book": [
    {
      "level": 1,
      "bidPrice": 25100,
      "bidQuantity": 2480,
      "bidOrders": 1,
      "askPrice": 25100,
      "askQuantity": 32235,
      "askOrders": 3
    }
  ]
}
```

Python code uses `snake_case`. Serialized JSON and custom database fields use `camelCase`.

## WorkerB and MySQL

`workers/worker_b.py` asynchronously transfers Redis messages to MySQL using SQLAlchemy 2.x.

For each Redis Stream message, WorkerB:

1. validates the message
2. opens a MySQL transaction
3. inserts the record into `RTDS`
4. commits the transaction
5. acknowledges the Redis message after the commit

The Redis Stream message ID is stored as `redisMessageId` and is unique, which prevents duplicate rows if a message is delivered again after a restart.

The main market-data table is exactly:

```text
RTDS
```

The database also contains Django tables for users, authentication, groups, permissions, sessions, and user profiles.

## Django

Django runs on:

```text
http://127.0.0.1:6280/app/
```

Users can:

- log in
- view their own profile
- change first name
- change last name
- change email
- upload/change their profile photo

Administrators can manage:

- name
- email
- photo
- user level
- groups
- permissions

## FastAPI

FastAPI runs on port `6288` under `/api`.

The required API endpoints are protected with the static API key from `.env`:

```http
X-API-Key: <API_KEY>
```

Required endpoints:

```text
GET /api/users/get/profile/{userid}
GET /api/users/get/photo/{userid}
GET /api/RTDS/get/current/{id}
GET /api/RTDS/get/historical/{id}
```

Behavior:

- `/api/users/get/profile/{userid}` returns profile data without credentials or photo.
- `/api/users/get/photo/{userid}` returns the profile picture as Base64.
- `/api/RTDS/get/current/{id}` returns the newest stored record for the requested instrument.
- `/api/RTDS/get/historical/{id}` returns historical records for the requested instrument as a JSON array.

Example:

```bash
curl \
  -H 'X-API-Key: DadeKavan-PD-X-API-KEY-CHANGE-ME' \
  http://127.0.0.1:6288/api/RTDS/get/current/35425587644337450
```

## Reliability and design decisions

The implementation includes:

- asynchronous WorkerA and WorkerB
- concurrent TSETMC requests
- retry/backoff for connection failures
- graceful handling of temporary TSETMC timeouts
- Redis Stream durability in addition to the required Pub/Sub channel
- MySQL transactions
- Redis acknowledgement only after successful database commit
- idempotency using Redis Stream message IDs
- processing of pending Redis messages after WorkerB restarts
- Docker health checks and restart policies
- worker heartbeat/progress logging
- FastAPI Swagger/OpenAPI documentation
- indexed MySQL queries for current and historical market data

Redis Pub/Sub alone was not used for WorkerB persistence because Pub/Sub messages can be lost while a subscriber is offline. The Redis Stream provides durable delivery while keeping the required Pub/Sub behavior.

Kafka was considered unnecessary for the scope of this assignment because Redis already satisfies the required architecture with less infrastructure.

Profile photos are stored using Django media storage. MinIO could be used as an alternative object-storage solution.

## TSETMC availability

Real TSETMC access is used with:

```dotenv
TSETMC_MOCK=false
```

If TSETMC is temporarily unavailable or inaccessible from the current network, mock mode can be enabled:

```dotenv
TSETMC_MOCK=true
```

The downstream Redis, WorkerB, MySQL, Django, and FastAPI components continue to work unchanged.


## Monitoring

Prometheus collects metrics from WorkerA and WorkerB, and Grafana provides an automatically provisioned worker dashboard.

Start the application with monitoring:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up --build -d
```

Open:

- Grafana: `http://127.0.0.1:3000`
- Prometheus: `http://127.0.0.1:9090`

Grafana credentials are loaded from `.env`. The `DadeKavan-PD-X Worker Monitoring` dashboard shows worker availability, throughput, failures, polling-cycle duration, batch sizes, and last successful activity.

## Tests

Run:

```bash
python -m pytest -q
```

or inside Docker:

```bash
docker compose exec worker-a python -m pytest -q
```

The tests cover schema serialization and TSETMC order-book parsing behavior.