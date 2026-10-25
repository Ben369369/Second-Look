from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import Settings, load_settings
from app.data.loader import ScenarioRegistry
from app.errors import install_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(
        title="Second Look API",
        version="0.1.0",
        description="Bounded tactical investigations over synthetic football data.",
    )
    app.state.settings = settings
    app.state.registry = ScenarioRegistry(settings.fixtures_dir)
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
