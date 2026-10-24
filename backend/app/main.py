from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .ai.router import router as ai_router  # noqa: E402
from .commerce.router import router as commerce_router  # noqa: E402
from .store import DATA_DIR  # noqa: E402

app = FastAPI(title="dresstoimpress API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=DATA_DIR), name="static")


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(ai_router)
app.include_router(commerce_router)  # /feed /products /swipe /cart /wishlist /checkout
