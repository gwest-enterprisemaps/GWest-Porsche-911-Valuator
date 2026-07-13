"""FastAPI entrypoint. Serves the SPA and the stateless valuation API.

Run locally:   uvicorn app.main:app --reload
Deploy:        uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import base64
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

load_dotenv()

from app.agent import MODEL, ValuationAgent  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("valuator")

MAX_PHOTOS = int(os.getenv("MAX_UPLOAD_PHOTOS", "5"))
MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Each valuation costs real API tokens — rate-limit per client IP.
# Format: slowapi/limits syntax, multiple limits separated by ';'.
RATE_LIMIT = os.getenv("RATE_LIMIT", "5/minute;30/day")


def client_ip(request: Request) -> str:
    """Proxy-aware client IP: hosts like Render/Railway sit behind a proxy,
    so trust the first hop in X-Forwarded-For when present."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip)

agent = ValuationAgent()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set — copy .env.example to .env")
    await agent.start()
    log.info("MCP session up — tools: %s", [t["name"] for t in agent.mcp_tools])
    yield
    await agent.stop()


app = FastAPI(title="Porsche 911 Valuator", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "model": MODEL, "mcp_tools": [t["name"] for t in agent.mcp_tools]}


@app.post("/api/valuate")
@limiter.limit(RATE_LIMIT)
async def valuate(
    request: Request,
    year: int = Form(...),
    trim: str = Form(...),
    mileage: int = Form(...),
    transmission: str = Form(...),
    exterior_color: str = Form(""),
    options: str = Form(""),
    history: str = Form(""),
    region: str = Form("United States"),
    photos: list[UploadFile] = File(default=[]),
) -> dict:
    """Stateless valuation: photos and specs live only in this request's memory."""
    if not (1964 <= year <= 2027):
        raise HTTPException(422, "Model year out of range")
    if not (0 <= mileage <= 500_000):
        raise HTTPException(422, "Mileage out of range")
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(422, f"Maximum {MAX_PHOTOS} photos")

    images: list[tuple[str, str]] = []
    for photo in photos:
        if not photo.filename:
            continue
        if photo.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(422, f"Unsupported image type: {photo.content_type}")
        raw = await photo.read()  # in memory only — never written to disk
        if len(raw) > MAX_PHOTO_BYTES:
            raise HTTPException(422, f"{photo.filename} exceeds 5 MB")
        images.append((photo.content_type, base64.standard_b64encode(raw).decode()))

    specs = {
        "model_year": year,
        "trim": trim,
        "mileage": mileage,
        "transmission": transmission,
        "exterior_color": exterior_color or "not specified",
        "notable_options": options or "not specified",
        "history_notes": history or "not specified",
        "region": region,
    }

    log.info("Valuating %s 911 %s, %s mi, %d photo(s)", year, trim, mileage, len(images))
    try:
        report = await agent.valuate(specs, images)
    except Exception:
        log.exception("Valuation failed")
        raise HTTPException(502, "Valuation failed — check server logs")
    return report


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
