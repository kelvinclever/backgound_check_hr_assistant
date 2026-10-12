import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import candidates, checks, consent, employer
from app.config import get_settings
from app.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # use Alembic migrations for production schema changes
    Path(get_settings().upload_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Pre-Employment Background Check Agent", version="2.0", lifespan=lifespan)

_origins = get_settings().cors_origin_list
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

app.include_router(candidates.router)
app.include_router(consent.router)
app.include_router(checks.router)
app.include_router(employer.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
