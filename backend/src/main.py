from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.errors import register_exception_handlers
from src.core.config import get_settings
from src.core.job_worker import start_job_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = start_job_worker()
    yield
    worker_task.cancel()


app = FastAPI(title="ContextOS API", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.ask import router as ask_router  # noqa: E402
from src.api.auth import router as auth_router  # noqa: E402
from src.api.connectors import router as connectors_router  # noqa: E402

# Importing api.ingest also runs services.ingestion_svc at module load time,
# which registers its job handlers with the worker (T022/T039) — this must
# happen before the lifespan's start_job_worker() call above runs the loop.
from src.api.ingest import router as ingest_router  # noqa: E402
from src.api.workspaces import router as workspaces_router  # noqa: E402

app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(connectors_router)
app.include_router(ingest_router)
app.include_router(ask_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
