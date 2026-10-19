# handles NotFoundErrors and turns them into JSON errors

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class NotFoundError(AppError):
    status_code, code = 404, "not_found"

class ConflictError(AppError):
    status_code, code = 409, "conflict"

class AuthenticationError(AppError):
    status_code, code = 401, "unauthenticated"

class ValidationFailed(AppError):
    status_code, code = 422, "invalid"

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle(_: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
            headers=headers,
        )