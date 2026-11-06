"""
FastAPI application entry point
────────────────────────────────
Mounts:
  /api        → API router (health, chat, ingest)
  /static     → CSS / JS assets
  /           → Jinja2 HTML templates
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.core.config import BASE_DIR, get_settings
from app.core.logging import configure_logging
from app.services.audit import init_db

# ── Bootstrap ─────────────────────────────────────────────────────────────────
settings = get_settings()
configure_logging(app_env=settings.app_env)
init_db()

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In production, replace "*" with the exact Render URL once it is known.
_cors_origins = (
    ["*"] if settings.app_env == "development"
    else [
        "https://your-app-name.onrender.com",  # update after first deploy
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.app_name},
    )
