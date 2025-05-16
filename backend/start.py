"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

logger = logging.getLogger(__name__)


from backend.auth import auth_backend, fastapi_users, github_oauth_client, google_oauth_client
from backend.config import settings
from backend.db import init_db
from backend.routers import admin, analytics, bug_reports, favorites, query
from backend.schemas.users import UserCreate, UserRead, UserUpdate
from backend.tasks.function_introspection import introspect
from backend.tasks.scheduler import start_scheduler
from backend.utils.logging_config import (
    EndpointLoggingRoute,
    RequestLoggingMiddleware,
    setup_endpoint_logging,
    setup_logging,
)

# Set up logging
setup_logging()

# Set up endpoint logging
setup_endpoint_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")

    # Initialize database first
    await init_db()

    logger.info("Starting function discovery...")
    discovery = introspect()
    discovery.discover_functions(
        exclude_patterns=[
            "backend.services.crawler.routes.*",
            "backend.services.crawler.*",
        ]
    )
    logger.info(f"Function discovery completed. Found {len(discovery.list_functions())} functions.")

    os.environ["CRAWLEE_MEMORY_MBYTES"] = "20480"  # 20GB

    start_scheduler()
    yield
    logger.info("Shutting down application")


# Determine route class based on settings
route_class = EndpointLoggingRoute if settings.logging.enable_endpoint_logging else APIRoute

# Create FastAPI app with custom route class
app = FastAPI(
    title="Reduse",
    version="0.1.0",
    route_class=route_class,  # Use determined route class
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware conditionally
if settings.logging.enable_endpoint_logging:
    app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(analytics.router)
app.include_router(query.router)
app.include_router(bug_reports.router)
app.include_router(admin.router)
app.include_router(favorites.router)

# Include FastAPI Users routers
## /login /logout
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
## /register
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
## /forgot-password /reset-password
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
## /request-verify-token /verify
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
# TODO: add /oauth
app.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client, auth_backend, "SECRET", is_verified_by_default=True  # TODO change
    ),
    prefix="/auth/oauth/google",
    tags=["auth"],
)
