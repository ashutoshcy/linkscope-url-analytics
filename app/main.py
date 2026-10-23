from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import database_url, secret_key
from app.db.models import Base
from app.api.auth import router as auth_router
from app.api.links import router as links_router, redirect_link
from app.api.stats import router as analytics_router

STATIC = Path(__file__).parent / "static"


def create_app(db_url: str | None = None) -> FastAPI:
    secret_key()  # fail at startup rather than issuing unsafe production sessions
    url = db_url or database_url()
    opts = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    if url == "sqlite://":
        opts["poolclass"] = StaticPool
    engine = create_engine(url, **opts)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(bind=engine)  # local quickstart; Alembic used for deployments
        yield
        engine.dispose()

    app = FastAPI(title="Linkscope API", version="1.0.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.state.session_factory = session_factory
    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(links_router, prefix="/api/links", tags=["Links"])
    app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/api/health", tags=["System"])
    def health():
        return {"status": "ok", "service": "linkscope", "version": "1.0.0"}

    @app.get("/r/{slug}", include_in_schema=False)
    def follow(slug: str, request: Request):
        return redirect_link(slug, request, session_factory)

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        # Do not leak database errors or other internal details.
        import logging
        logging.getLogger("linkscope").exception("Unhandled request error", exc_info=exc)
        return JSONResponse({"detail": "Unexpected server error"}, status_code=500)

    return app

app = create_app()
