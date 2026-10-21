from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS
from app.db import Base, engine
from app.routers import (
    assets, briefr, brokers, calendar, fundamentals, gardnr, income, listr, notr, gripr, performance, portfolios, positions,
    summary,
    taskr, trainr, transactions,
)

# Local single-user app: tables are created directly from the models rather than requiring
# an Alembic migration run before first use. Alembic is still used for schema changes going
# forward (see alembic/).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="gainr")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolios.router)
app.include_router(summary.router)
app.include_router(positions.router)
app.include_router(performance.router)
app.include_router(income.router)
app.include_router(transactions.router)
app.include_router(assets.router)
app.include_router(brokers.router)
app.include_router(fundamentals.router)
app.include_router(fundamentals.catalog_router)
app.include_router(calendar.router)
app.include_router(gripr.router)
app.include_router(listr.router)
app.include_router(gardnr.router)
app.include_router(trainr.router)
app.include_router(taskr.router)
app.include_router(briefr.router)
app.include_router(notr.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# In production the built frontend ships alongside the backend so one process serves both; in
# local dev this directory doesn't exist and Vite's own dev server + proxy handles the frontend
# instead.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    FRONTEND_DIST_RESOLVED = FRONTEND_DIST.resolve()
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        # A route the routers above didn't claim under /api is a real 404, not a page to render.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        # A real file at the root (favicon, manifest, ...) is served as-is; anything else is a
        # client-side route (react-router), which only index.html knows how to handle.
        # Resolved and re-checked against FRONTEND_DIST: `full_path` is attacker-controlled
        # (e.g. "../../../../etc/passwd"), and Path's `/` operator doesn't strip ".." segments,
        # so an unresolved join would let a request escape the frontend directory entirely.
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_relative_to(FRONTEND_DIST_RESOLVED) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
