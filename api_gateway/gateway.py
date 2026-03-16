"""
api_gateway/gateway.py

Lightweight API Gateway — single entry point between the React frontend
and the backend recommendation microservice.

Responsibilities:
  - Accept all frontend traffic on port 8080
  - Forward /recommend and /health to the backend microservice (port 8000)
  - Add request logging and timing headers
  - Handle backend errors gracefully

Run:
    uvicorn api_gateway.gateway:app --port 8080 --reload
"""

import time
import httpx

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
load_dotenv()

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import get_logger

log = get_logger("api_gateway")

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT_SECONDS = 120   # agent pipeline can take ~30-60s

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Course Finder — API Gateway",
    description="Entry point that routes frontend requests to the backend microservice.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Gateway"])
def gateway_health():
    """Gateway liveness check."""
    return {"status": "ok", "service": "API Gateway", "backend": BACKEND_URL}


@app.post("/recommend", tags=["Gateway"])
async def proxy_recommend(request: Request):
    """
    Proxy POST /recommend → backend microservice /recommend.
    """
    t0 = time.perf_counter()
    body = await request.body()

    log.info("[Gateway] POST /recommend | body_size=%d bytes", len(body))

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{BACKEND_URL}/recommend",
                content=body,
                headers={"Content-Type": "application/json"},
            )
    except httpx.ConnectError:
        log.error("[Gateway] Backend unreachable at %s", BACKEND_URL)
        raise HTTPException(
            status_code=503,
            detail=f"Backend microservice is unavailable. Make sure it's running at {BACKEND_URL}",
        )
    except httpx.TimeoutException:
        log.error("[Gateway] Backend timed out after %ss", TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=504,
            detail="Backend microservice timed out.",
        )

    elapsed = time.perf_counter() - t0
    log.info(
        "[Gateway] POST /recommend → %d | elapsed=%.2fs",
        response.status_code, elapsed,
    )

    return JSONResponse(
        content=response.json(),
        status_code=response.status_code,
        headers={"X-Gateway-Time": f"{elapsed:.2f}s"},
    )
