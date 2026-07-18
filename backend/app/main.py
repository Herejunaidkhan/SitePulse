from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api.routes import router

app = FastAPI(title="SitePulse API", version="0.1.0")

_default_origins = "http://localhost:5174,http://127.0.0.1:5174"
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def _needs_seed() -> bool:
    """SQLite: seed on first run (file doesn't exist yet). Postgres: seed only if empty."""
    if not os.environ.get("DATABASE_URL"):
        return not os.path.exists(db._DB_PATH)
    db.init_db()
    session = db.SessionLocal()
    try:
        return session.query(db.Organization).first() is None
    finally:
        session.close()


@app.on_event("startup")
def startup():
    if _needs_seed():
        from app.seed import seed
        seed()
    else:
        db.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
