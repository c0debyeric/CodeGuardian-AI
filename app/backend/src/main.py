"""FastAPI application entry point."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.admin import router as admin_router
from src.api.routes import router
from src.core.config import get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        from src.usage.db import init_db

        logger.info(
            "Starting LLM Gateway",
            version=settings.app_version,
            environment=settings.app_env,
        )
        try:
            await init_db()
        except Exception as e:
            logger.warning("db.init_failed", error=str(e))
        yield
        logger.info("Shutting down LLM Gateway")

    app = FastAPI(
        title=settings.app_name,
        description=(
            "OpenAI-compatible LLM gateway with multi-provider routing, "
            "fallback, cost tracking, and observability."
        ),
        version=settings.app_version,
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router)
    app.include_router(admin_router)

    # Prometheus metrics endpoint
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # OpenTelemetry auto-instrumentation
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({
                "service.name": os.environ.get("OTEL_SERVICE_NAME", "llm-gateway"),
            })
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)

            FastAPIInstrumentor.instrument_app(app)
            BotocoreInstrumentor().instrument()

            logger.info("OpenTelemetry instrumentation enabled")
        except Exception as e:
            logger.warning("Failed to initialize OpenTelemetry", error=str(e))

    return app


# Create the app instance
app = create_app()
