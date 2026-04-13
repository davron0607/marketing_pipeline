# Survey Analytics Platform

A production-lean MVP for uploading survey datasets, detecting fraud, and generating analytics reports.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, App Router, Tailwind CSS |
| Backend API | FastAPI, Python 3.12, SQLAlchemy async |
| Async Workers | Celery |
| Queue / Event Buffer | Redis Streams |
| Database | PostgreSQL 16 |
| Object Storage | MinIO |
| Local Dev | Docker Compose |

## Folder Structure

```
marketing_pipeline/
├── apps/
│   ├── web/          # Next.js frontend
│   ├── api/          # FastAPI backend
│   └── worker/       # Celery worker
├── infra/
│   ├── nginx/
│   └── minio/
├── docs/
└── docker-compose.yml
```

## Quick Start

### Prerequisites
- Docker Desktop ≥ 4.x
- Docker Compose v2

### 1. Clone and start

```bash
git clone https://github.com/davron0607/marketing_pipeline.git
cd marketing_pipeline
docker compose up --build
```

### 2. Services

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API + Swagger | http://localhost:8000/api/docs |
| MinIO Console | http://localhost:9001 (minioadmin / minioadmin) |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. Create your first user

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password123","full_name":"Admin"}'
```

Then log in at http://localhost:3000/login.

### 4. Run migrations manually (if needed)

```bash
docker compose exec api alembic upgrade head
```

## Development (without Docker)

### API

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DATABASE_URL, REDIS_URL etc.
alembic upgrade head
uvicorn app.main:app --reload
```

### Worker

```bash
cd apps/worker
pip install -r requirements.txt
celery -A app.celery_app:celery_app worker --loglevel=info
```

### Frontend

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Environment Variables

### API / Worker

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/survey_analytics` | Postgres connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO host:port |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `SECRET_KEY` | `change-me-in-production` | JWT signing secret |

### Web

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API base URL |

## API Endpoints

| Module | Endpoints |
|--------|-----------|
| Auth | `POST /api/v1/auth/login`, `/register`, `GET /me` |
| Projects | CRUD `/api/v1/projects` |
| Uploads | `POST/GET /api/v1/uploads/project/{id}` |
| Jobs | `POST/GET /api/v1/jobs`, `GET /api/v1/jobs/{id}` |
| Fraud | `GET /api/v1/fraud/project/{id}` |
| Analytics | `GET /api/v1/analytics/project/{id}` |
| Reports | `GET /api/v1/reports/project/{id}`, `GET /{id}/download` |
