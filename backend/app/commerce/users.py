"""Users + onboarding: /users CRUD and /onboarding (Nabil).

Onboarding text like "Y2K, tops under $40" is parsed by rules (no AI, free, instant) into style tags and
per-category budgets in the `_in_budget` format: {category: [min, max]}. Adam's /users/{id}/body-photo and
/users/{id}/style(/apply) live in ai/router.py; this module doesn't touch them.
"""
from __future__ import annotations

import re
import uuid
from typing import Annotated, Optional, get_args

from fastapi import APIRouter, HTTPException
from pydantic import AfterValidator, BaseModel, Field

from ..models import Category, StyleTag, User
from ..store import store

router = APIRouter(tags=["users"])
CATEGORIES = list(get_args(Category))
STYLES = set(get_args(StyleTag))
DEMO_FRIENDS = ("u_adam", "u_nabil", "u_ryan")

STYLE_SYN = {"street": "streetwear", "minimal": "minimalist", "athletic": "athleisure", "gym": "athleisure",
             "office": "business", "work": "business", "90s": "vintage", "retro": "vintage"}
CAT_SYN = {w: c for c, ws in {
    "top": "top tops tee tees t-shirt t-shirts tshirt tshirts shirt shirts hoodie hoodies sweater sweaters",
    "bottom": "bottom bottoms jeans pants trousers shorts skirt skirts",
    "outerwear": "outerwear jacket jackets coat coats",
    "shoes": "shoes shoe sneakers sneaker boots boot",
    "dress": "dress dresses",
    "accessory": "accessory accessories bag bags",
}.items() for w in ws.split()}
FILLER = set("a an the and or for my i im i'm like love want prefer with in of stuff things items clothes "
             "everything anything all style styles vibe vibes".split())

NUM = r"\$?\s*(\d+(?:\.\d+)?)"
BUDGET = re.compile(
    rf"(?:from\s+)?{NUM}\s*(?:-|–|to)\s*{NUM}"                                          # $20-$60, 20 to 60
    rf"|(?:under|below|less than|<=?|max(?:imum)?|up to|at most|no more than)\s*{NUM}"  # under $40
    rf"|(?:around|about|roughly|~)\s*{NUM}"                                             # around $50
    r"|\$(\d+(?:\.\d+)?)", re.I)                                                        # bare $40 = max
WORD = re.compile(r"[a-z0-9']+(?:-[a-z0-9]+)*")


def _budget(m: re.Match) -> list[float]:
    lo, hi, mx, mid, bare = m.groups()
    if lo:
        a, b = sorted((float(lo), float(hi)))
        return [a, b]
    if mid:
        return [round(float(mid) * 0.7, 2), round(float(mid) * 1.3, 2)]
    return [0.0, float(mx or bare)]


def parse_prefs(text: str) -> dict:
    """"Y2K, tops under $40" -> {styles: ["y2k"], budgets: {"top": [0, 40]}, unmatched: ""}.
    A budget attaches to the nearest category before it in its clause (else the first after it, else all)."""
    text = re.sub(r"between\s+(\$?\s*\d+(?:\.\d+)?)\s+and\s+(\$?\s*\d+(?:\.\d+)?)", r"\1-\2", (text or "").lower())
    styles, budgets, left = [], {}, []
    for clause in re.split(r"[,;&\n]|\band\b|\bplus\b", text):
        cats = [(w.start(), CAT_SYN[w.group()]) for w in WORD.finditer(clause) if w.group() in CAT_SYN]
        for m in BUDGET.finditer(clause):
            before = [c for pos, c in cats if pos < m.start()]
            after = [c for pos, c in cats if pos > m.start()]
            for c in [before[-1]] if before else [after[0]] if after else CATEGORIES:
                budgets[c] = _budget(m)
        for w in WORD.findall(BUDGET.sub(" ", clause)):
            tag = w if w in STYLES else STYLE_SYN.get(w)
            if tag:
                styles += [tag] if tag not in styles else []
            elif w not in CAT_SYN and w not in FILLER:
                left.append(w)
    return {"styles": styles, "budgets": budgets, "unmatched": " ".join(left)}


def _check_ranges(v: Optional[dict]) -> Optional[dict]:
    for k, r in (v or {}).items():
        if k not in CATEGORIES or len(r) != 2 or r[0] > r[1]:
            raise ValueError(f"price_ranges.{k} must be a category -> [min, max]")
    return v


Ranges = Annotated[Optional[dict[str, list[float]]], AfterValidator(_check_ranges)]


class UserCreate(BaseModel):
    id: Optional[str] = Field(None, min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=60)
    style_text: str = Field("", max_length=500)
    price_ranges: Ranges = None
    friends: list[str] = []


class UserPatch(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=60)
    style_text: Optional[str] = Field(None, max_length=500)
    price_ranges: Ranges = None
    friends: Optional[list[str]] = None


class Onboarding(BaseModel):
    user_id: Optional[str] = Field(None, min_length=1, max_length=64)
    display_name: Optional[str] = Field(None, min_length=1, max_length=60)
    text: str = Field("", max_length=500)


def _new_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:20] or "user"
    return f"u_{slug}-{uuid.uuid4().hex[:4]}"


def _get(user_id: str) -> dict:
    user = store.get("users", user_id)
    if not user:
        raise HTTPException(404, "unknown user")
    return user


def _save(user: dict) -> dict:
    user = User(**user).model_dump()
    store.put("users", user["id"], user)
    return user


@router.post("/users", response_model=User)
def create_user(req: UserCreate):
    uid = req.id or _new_id(req.display_name)
    if store.get("users", uid):
        raise HTTPException(409, "user already exists")
    ranges = req.price_ranges if req.price_ranges is not None else parse_prefs(req.style_text)["budgets"]
    return _save({"id": uid, "display_name": req.display_name, "style_text": req.style_text,
                  "price_ranges": ranges, "friends": req.friends})


@router.get("/users/{user_id}", response_model=User)
def get_user(user_id: str):
    return _get(user_id)


@router.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: str, req: UserPatch):
    """Partial update. New style_text without price_ranges re-parses budgets and merges them over the old ones."""
    user = _get(user_id)
    sent = req.model_dump(exclude_unset=True, exclude_none=True)
    if "style_text" in sent and "price_ranges" not in sent and sent["style_text"] != user.get("style_text"):
        sent["price_ranges"] = {**(user.get("price_ranges") or {}), **parse_prefs(sent["style_text"])["budgets"]}
    return _save({**user, **sent})


@router.post("/onboarding")
def onboarding(req: Onboarding):
    """One call for the demo: create or update the user from free text, return what was understood."""
    parsed = parse_prefs(req.text)
    user = store.get("users", req.user_id) if req.user_id else None
    if user:
        user = {**user, "style_text": req.text,
                "price_ranges": {**(user.get("price_ranges") or {}), **parsed["budgets"]}}
        if req.display_name:
            user["display_name"] = req.display_name
    else:
        name = req.display_name or req.user_id or "You"
        uid = req.user_id or _new_id(name)
        user = {"id": uid, "display_name": name, "style_text": req.text, "price_ranges": parsed["budgets"],
                "friends": [f for f in DEMO_FRIENDS if f != uid and store.get("users", f)]}
    return {"user": _save(user), "parsed": parsed}
