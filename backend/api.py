from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Literal
from fastapi import HTTPException
from fastapi import Request
from contextlib import asynccontextmanager
import json
import time
import uuid

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.extension import (
    _rate_limit_exceeded_handler
)

from backend.database import (
    init_db,
    insert_ads,
    get_connection,
)

from backend.services.recommender_engine import (
    recommender_engine
)
from backend.config.config import ADMIND_ENV, validate_production_settings

# ─────────────────────────────────────────────────────
# FASTAPI INIT
# ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app):
    validate_production_settings()
    init_db()
    if ADMIND_ENV != "production":
        insert_ads()
    yield


app = FastAPI(title="AdMind API", lifespan=lifespan)

# ─────────────────────────────────────────────────────
# RATE LIMITER
# ─────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

app.add_middleware(
    SlowAPIMiddleware
)


class RequestBodyLimitMiddleware:
    """Buffer only small JSON requests and reject oversized bodies before parsing."""

    def __init__(self, app, max_bytes=16 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = next(
            (value for key, value in scope.get("headers", []) if key.lower() == b"content-length"),
            None,
        )
        try:
            if content_length is not None and int(content_length) > self.max_bytes:
                await self._reject(send)
                return
        except ValueError:
            await self._reject(send)
            return

        messages = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    await self._reject(send)
                    return
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                return

        async def replay():
            return messages.pop(0) if messages else {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(send):
        body = b'{"detail":"Request body too large"}'
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


app.add_middleware(RequestBodyLimitMiddleware, max_bytes=16 * 1024)


@app.middleware("http")
async def log_request_metrics(request, call_next):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("Unhandled API request failed; exception_type=%s", type(exc).__name__)
        raise
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(json.dumps({
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": elapsed_ms,
    }, separators=(",", ":")))
    return response

# ─────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────
# DATABASE INIT
# ─────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────
# REQUEST MODEL
# ─────────────────────────────────────────────────────

class RequestData(BaseModel):

    title: str = Field(min_length=1, max_length=500)

    mode: Literal["study", "focus", "casual", "silent"]

    user_type: Literal["student", "developer", "gamer", "professional", "casual"] = "casual"

# ─────────────────────────────────────────────────────
# HOME ROUTE
# ─────────────────────────────────────────────────────

@app.get("/")

def home():

    return {

        "message": "AdMind API running"
    }

# ─────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────

@app.get("/livez")
def livez():
    return {"status": "alive"}


@app.get("/health")
@app.get("/readyz")

def health():
    """Report readiness only when the database and usable ad catalogue exist."""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
            count = conn.execute(
                "SELECT COUNT(*) FROM ads "
                "WHERE trim(COALESCE(ad_name, '')) <> '' "
                "AND trim(COALESCE(description, '')) <> ''"
            ).fetchone()[0]
        if count < 1:
            logger.warning("API readiness check failed: no usable ads in catalogue")
            raise HTTPException(status_code=503, detail="Service dependencies unavailable")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API readiness check failed; exception_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Service dependencies unavailable")
    return {"status": "healthy"}

# ─────────────────────────────────────────────────────
# RECOMMENDATION ROUTE
# ─────────────────────────────────────────────────────

@app.post("/recommend-ad")

@limiter.limit("10/minute")

def recommend(

    request: Request,

    data: RequestData
):

    try:

        result = recommender_engine.rank(

            data.title,

            data.mode,

            data.user_type
        )

        return result

    except Exception as exc:
        logger.error("Recommendation failed; exception_type=%s", type(exc).__name__)

        raise HTTPException(

            status_code=500,

            detail="Internal recommendation error"
        )
