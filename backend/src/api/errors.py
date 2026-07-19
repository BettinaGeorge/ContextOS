from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for application-level errors that map to the shared error
    shape in contracts/api.md: { "error": str, "detail": str | None }."""

    def __init__(self, error: str, detail: str | None = None, status_code: int = 400):
        self.error = error
        self.detail = detail
        self.status_code = status_code


class NotFoundError(DomainError):
    def __init__(self, error: str, detail: str | None = None):
        super().__init__(error, detail, status_code=status.HTTP_404_NOT_FOUND)


class ConflictError(DomainError):
    def __init__(self, error: str, detail: str | None = None):
        super().__init__(error, detail, status_code=status.HTTP_409_CONFLICT)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"error": exc.error, "detail": exc.detail}
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "detail": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "validation_error", "detail": str(exc.errors())},
        )
