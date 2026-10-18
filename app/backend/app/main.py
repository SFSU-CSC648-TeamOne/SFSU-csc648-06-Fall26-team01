# creating FastAPI app, turns on CORS (Cross origin), handles errors
# and mounts all files under /api

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ascenda API", version="0.1.0",
        docs_url=f"{settings.api_prefix}/docs", openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root():
        return {"message": "Ascenda API is running", "docs": f"{settings.api_prefix}/docs"}

    return app


app = create_app()