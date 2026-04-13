# Architecture

## Overview

Survey Analytics Platform is a monorepo with three main applications:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser                                  │
│                    Next.js (port 3000)                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / REST
┌──────────────────────────▼──────────────────────────────────────┐
│                    FastAPI (port 8000)                          │
│          auth · projects · uploads · jobs · fraud               │
│                  analytics · reports                            │
└──────┬────────────────────┬──────────────────────────┬──────────┘
       │                    │                          │
┌──────▼──────┐  ┌──────────▼────────┐  ┌─────────────▼──────────┐
│ PostgreSQL  │  │  Redis (Streams)  │  │       MinIO             │
│  (data)     │  │  Celery broker    │  │  (file storage)         │
└─────────────┘  └──────────┬────────┘  └────────────────────────┘
                            │
              ┌─────────────▼──────────┐
              │    Celery Worker       │
              │  fraud · reports       │
              └────────────────────────┘
```

## Data Flow

1. User uploads CSV/XLSX → API stores in MinIO, records metadata in Postgres
2. User triggers analysis → API creates Job record, dispatches Celery task
3. Worker pulls file from MinIO, runs fraud detection + report generation
4. Worker writes FraudResult rows and Report rows back to Postgres
5. Frontend polls job status, displays results when complete

## Fraud Detection

- **Straight-lining**: respondent answered all numeric questions identically
- **Duplicate response**: exact copy of another row's answers

## Clean Architecture Layers

| Layer | Responsibility |
|-------|---------------|
| `routers/` | HTTP request parsing, auth, response serialization |
| `services/` | Business logic, orchestration |
| `repositories/` | DB queries, pure data access |
| `models/` | SQLAlchemy ORM table definitions |
| `schemas/` | Pydantic I/O validation |
