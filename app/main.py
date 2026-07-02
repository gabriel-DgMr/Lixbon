"""
main.py — Punto de entrada de FOLAX DTC v2.0
Configura la app FastAPI, middlewares, ciclo de vida y registra todos los routers.
"""
from __future__ import annotations
import threading
import time
import mimetypes

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import deps
from app.config import ALLOWED_ORIGINS, APP_DESCRIPTION, APP_TITLE, APP_VERSION, LOGS_DIR
from app.db import archive_old_inactive_keys, init_db
from app.security import security_headers_middleware
from app.routers import admin, auth, chat, installer, keys, versions, ws_status, monitor

# ── App FastAPI ────────────────────────────────────────────────────────────

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
)

# ── Middleware: CORS ───────────────────────────────────────────────────────
_cors_origins = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
_cors_origins.append("http://localhost:5173") # Vite dev server

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Middleware: Headers de seguridad HTTP ──────────────────────────────────
app.middleware("http")(security_headers_middleware)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(chat.router)
app.include_router(installer.router)
app.include_router(versions.router)
app.include_router(ws_status.router)
app.include_router(monitor.router)
app.include_router(admin.router)   # Incluir último: tiene GET "/" (dashboard)


# ── Ciclo de vida ──────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Inicializa BD, clientes HTTP y el orquestador de nodos."""
    mimetypes.add_type('application/x-msi', '.msi')
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    versions.sync_versions_to_db()

    deps.http_client_fast = httpx.AsyncClient(timeout=10.0)
    deps.http_client_chat = httpx.AsyncClient(timeout=120.0)

    deps.orquestador.iniciar()
    _start_archiver_cron()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Cierra clientes HTTP y detiene el orquestador."""
    deps.orquestador.detener()
    if deps.http_client_fast is not None:
        await deps.http_client_fast.aclose()
    if deps.http_client_chat is not None:
        await deps.http_client_chat.aclose()


# ── Cron daemon de archivado de keys ──────────────────────────────────────

def _start_archiver_cron() -> None:
    """Hilo daemon que archiva API keys inactivas cada 24 horas."""
    import logging as _log

    def _run():
        while True:
            time.sleep(86400)
            try:
                n = archive_old_inactive_keys()
                if n:
                    _log.getLogger("folax").info(f"[cron] {n} API keys archivadas.")
            except Exception as exc:
                _log.getLogger("folax").warning(f"[cron] Error al archivar keys: {exc}")

    threading.Thread(target=_run, daemon=True, name="key-archiver").start()


# ── Servir Frontend (React SPA) ────────────────────────────────────────────
import pathlib as _pathlib
from fastapi import HTTPException
from fastapi.responses import FileResponse

_frontend_dist = _pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"

# Mount static files folder (e.g. for release downloads)
_static_dir = _pathlib.Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/{path_name:path}")
    async def serve_frontend(path_name: str):
        if path_name.startswith("api/") or path_name.startswith("v1/") or path_name.startswith("docs") or path_name.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(str(_frontend_dist / "index.html"))

