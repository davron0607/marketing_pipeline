import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, projects, uploads, jobs, fraud, analytics, reports, ingestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,       prefix="/api/v1/auth",      tags=["auth"])
app.include_router(projects.router,   prefix="/api/v1/projects",  tags=["projects"])
app.include_router(uploads.router,    prefix="/api/v1/uploads",   tags=["uploads"])
app.include_router(jobs.router,       prefix="/api/v1/jobs",      tags=["jobs"])
app.include_router(ingestion.router,  prefix="/api/v1",           tags=["ingestion"])
app.include_router(fraud.router,      prefix="/api/v1",           tags=["fraud"])
app.include_router(analytics.router,  prefix="/api/v1",           tags=["analytics"])
app.include_router(reports.router,    prefix="/api/v1",           tags=["reports"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME}
