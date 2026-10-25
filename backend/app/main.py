from dotenv import load_dotenv

load_dotenv()

import hmac  # noqa: E402
import os  # noqa: E402

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .ai.router import router as ai_router  # noqa: E402
from .auth import make_auth_guard, router as auth_router  # noqa: E402
from .commerce.discover import router as discover_router  # noqa: E402
from .commerce.fitcheck import router as fitcheck_router  # noqa: E402
from .commerce.fitcheck_extras import router as fitcheck_extras_router  # noqa: E402
from .commerce.fitcheck_web import router as fitcheck_web_router  # noqa: E402
from .commerce.reels import router as reels_router  # noqa: E402
from .commerce.router import router as commerce_router  # noqa: E402
from .commerce.search import router as search_router  # noqa: E402
from .commerce.users import router as users_router  # noqa: E402
from .store import DATA_DIR  # noqa: E402

# Shared key for a public tunnel (the repo is public, so a leaked URL could spend AI credits).
# Set API_SHARED_KEY in .env; clients send it as the X-DTI-Key header. Images and /health stay open
# because image widgets can't send headers (file names are random).
OPEN_PREFIXES = ("/health", "/static/")
# Public QR page for guests, gated by its own FITCHECK_EVENT_CODE. Matched exactly (or "/fit/...")
# so it never opens /fitcheck/*.
OPEN_EXACT = ("/fit", "/img")  # exact: a prefix would also open any future /img* or /fitcheck* route
OPEN_SUBTREES = ("/fit/",)


def _is_open(path: str) -> bool:
    return path.startswith(OPEN_PREFIXES) or path in OPEN_EXACT or path.startswith(OPEN_SUBTREES)


# Optional sign-in (app/auth.py): a valid `Authorization: Bearer` session token pins the request to its
# user (403 on a different user_id); no header = today's behaviour unless AUTH_REQUIRED=1.
app = FastAPI(title="dresstoimpress API", dependencies=[Depends(make_auth_guard(_is_open))])
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve only image folders. Never mount DATA_DIR itself: it holds the JSON store (users, closets, usage).
for _sub in ("uploads", "tryon"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)
    app.mount(f"/static/{_sub}", StaticFiles(directory=DATA_DIR / _sub), name=f"static-{_sub}")


@app.middleware("http")
async def shared_key(request: Request, call_next):
    key = os.getenv("API_SHARED_KEY", "")
    if key and request.method != "OPTIONS" and not _is_open(request.url.path):
        if not hmac.compare_digest(request.headers.get("x-dti-key", ""), key):
            return JSONResponse({"detail": "missing or wrong X-DTI-Key"}, status_code=401)
    return await call_next(request)


@app.get("/health")
def health():
    return {"ok": True}


@app.on_event("startup")
def _rebase_image_urls():
    # tunnel hostnames change on every restart: point stored /static image URLs at the current address
    if os.getenv("REBASE_STATIC_URLS", "1") != "0":
        from .static_urls import rebase_static_urls

        rebase_static_urls(os.getenv("PUBLIC_BASE", "http://localhost:8000"))


# Image proxy for the Flutter web build: retailer CDNs may not send CORS headers, which breaks
# images drawn on a canvas. Only these hosts are fetched (so it's not an open proxy), and it needs
# no key because image widgets can't send headers.
IMG_HOSTS = {"image.hm.com", "lp2.hm.com", "image.uniqlo.com", "picsum.photos", "fastly.picsum.photos",
             "images.unsplash.com", "cdn.shopify.com",  # cdn.shopify.com: the Shopify stores (sprint #2)
             "i.pinimg.com"}  # Discover board pins
IMG_MAX_BYTES = 8 * 1024 * 1024


@app.get("/img")
def image_proxy(url: str):
    import httpx
    from urllib.parse import urlparse

    from fastapi import HTTPException
    from fastapi.responses import Response

    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in IMG_HOSTS:
        raise HTTPException(400, "image host not allowed")
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
        r.raise_for_status()
    except Exception:  # noqa: BLE001
        raise HTTPException(502, "image fetch failed")
    if urlparse(str(r.url)).hostname not in IMG_HOSTS:
        raise HTTPException(400, "image host not allowed")  # redirected somewhere else
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("image/") or len(r.content) > IMG_MAX_BYTES:
        raise HTTPException(415, "not an image")
    return Response(r.content, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})


app.include_router(auth_router)  # /auth/google, /auth/logout, /auth/me
app.include_router(ai_router)
app.include_router(commerce_router)  # /feed /products /swipe /cart /wishlist /checkout
app.include_router(reels_router)  # Home reels: /feed/{user}/tryons prefetch + poll (sprint-4)
app.include_router(search_router)  # Discover: /search, /search/styles, /search/photo
app.include_router(discover_router)  # Discover board: /discover/board, /discover/pins/{id}/similar
app.include_router(fitcheck_extras_router)
app.include_router(fitcheck_router)  # /fitcheck posts, feed, tags, likes, comments, shop
app.include_router(users_router)  # /users CRUD, /onboarding
app.include_router(fitcheck_web_router)  # public /fit page for guests (event code, no X-DTI-Key)
