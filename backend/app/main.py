from dotenv import load_dotenv

load_dotenv()

import hmac  # noqa: E402
import os  # noqa: E402

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .ai.router import router as ai_router  # noqa: E402
from .commerce.router import router as commerce_router  # noqa: E402
from .store import DATA_DIR  # noqa: E402

app = FastAPI(title="dresstoimpress API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve only image folders. Never mount DATA_DIR itself: it holds the JSON store (users, closets, usage).
for _sub in ("uploads", "tryon"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)
    app.mount(f"/static/{_sub}", StaticFiles(directory=DATA_DIR / _sub), name=f"static-{_sub}")

# Shared key for a public tunnel (the repo is public, so a leaked URL could spend AI credits).
# Set API_SHARED_KEY in .env; clients send it as the X-DTI-Key header. Images and /health stay open
# because image widgets can't send headers (file names are random).
OPEN_PREFIXES = ("/health", "/static/")


@app.middleware("http")
async def shared_key(request: Request, call_next):
    key = os.getenv("API_SHARED_KEY", "")
    if key and request.method != "OPTIONS" and not request.url.path.startswith(OPEN_PREFIXES):
        if not hmac.compare_digest(request.headers.get("x-dti-key", ""), key):
            return JSONResponse({"detail": "missing or wrong X-DTI-Key"}, status_code=401)
    return await call_next(request)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(ai_router)
app.include_router(commerce_router)  # /feed /products /swipe /cart /wishlist /checkout
