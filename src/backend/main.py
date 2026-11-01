import hashlib
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

import frontend

from .api.main import api_router
from .config import BACKEND_RELOAD, FRONTEND_HOST, PROJECT_NAME
from .database import create_db_and_tables

FRONTEND_DIR = Path(frontend.__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


def custom_generate_unique_id(route: APIRoute) -> str:
    if not route.tags:
        raise ValueError(f"Endpoint senza tag: {route.path} (nome: {route.name})")

    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title=PROJECT_NAME,
    openapi_url="/openapi.json",
    lifespan=lifespan,
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix="/api/v1")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False, tags=["frontend"])
def read_root():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    static_files = sorted(
        path
        for directory in (FRONTEND_DIR / "css", FRONTEND_DIR / "js")
        for path in directory.rglob("*")
        if path.is_file()
    )
    fingerprint = hashlib.sha256()
    for path in static_files:
        fingerprint.update(path.relative_to(FRONTEND_DIR).as_posix().encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(path.read_bytes())

    return html.replace("__VERSION__", fingerprint.hexdigest()[:12])


def main() -> None:

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=2662,
        reload=BACKEND_RELOAD,
    )
