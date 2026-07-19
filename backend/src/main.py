from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.errors import register_exception_handlers
from src.core.job_worker import start_job_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = start_job_worker()
    yield
    worker_task.cancel()


app = FastAPI(title="ContextOS API", lifespan=lifespan)
register_exception_handlers(app)

# Routers are added incrementally as each is implemented (Phase 3+); importing
# here rather than at module scope above avoids a partial-app import error
# while api/workspaces.py, api/connectors.py, etc. are still being built out.
from src.api.auth import router as auth_router  # noqa: E402

app.include_router(auth_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
