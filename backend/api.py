from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import HTTPException
from fastapi import Request

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
    insert_ads
)

from backend.services.recommender_engine import (
    recommender_engine
)

# ─────────────────────────────────────────────────────
# FASTAPI INIT
# ─────────────────────────────────────────────────────

app = FastAPI(
    title="AdminAI API"
)

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

# ─────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────

logging.basicConfig(

    filename="api.log",

    level=logging.INFO,

    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────
# DATABASE INIT
# ─────────────────────────────────────────────────────

init_db()

insert_ads()

# ─────────────────────────────────────────────────────
# REQUEST MODEL
# ─────────────────────────────────────────────────────

class RequestData(BaseModel):

    title: str

    mode: str

    user_type: str = "casual"

# ─────────────────────────────────────────────────────
# HOME ROUTE
# ─────────────────────────────────────────────────────

@app.get("/")

def home():

    return {

        "message": "AdminAI API Running"
    }

# ─────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────

@app.get("/health")

def health():

    return {

        "status": "healthy"
    }

# ─────────────────────────────────────────────────────
# RECOMMENDATION ROUTE
# ─────────────────────────────────────────────────────

@app.post("/recommend-ad")

@limiter.limit("10/minute")

async def recommend(

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

    except Exception as e:

        logger.exception(
            "Recommendation failed"
        )

        raise HTTPException(

            status_code=500,

            detail="Internal recommendation error"
        )