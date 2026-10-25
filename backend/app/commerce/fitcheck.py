"""Fit Check (OOTD feed): /fitcheck posts, feed, tags, likes, comments, shop-this-fit (Nabil).

Collection fitcheck_posts: {id, user_id, photo_url, caption, tagged: [FitTag], created_at, likes: [user_id],
comments: [{id, user_id, text, created_at}], visibility: "friends" | "public", photo_w, photo_h}.
photo_w/photo_h: pixel size of an uploaded photo (read from our saved file); for an external URL, the size the
app sends with the JSON post (else null); null for posts made before the fields existed (the app lays photos out at their own aspect ratio, sprint-3 3.1).
Inspo is one feed for everyone (council D4): every user sees every post, so friends lists don't filter
anything here. `visibility` is still stored (the guest /fit wall only shows "public" posts).
Post views (feed, detail, create, tag edit) carry `comment_count` (the total) and `comments` = only the
PREVIEW_COMMENTS newest, oldest -> newest, shaped like GET .../comments items (with `author`); page the rest there.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from ..ai import service
from ..ai.router import _save_upload
from ..models import FitTag
from ..static_urls import local_static_path
from ..store import DATA_DIR, store
from .router import _dept_ok

log = logging.getLogger(__name__)
router = APIRouter(tags=["fitcheck"])
COL = "fitcheck_posts"


class PostCreate(BaseModel):
    user_id: str
    photo_url: str
    caption: str = Field("", max_length=500)
    tagged: list[FitTag] = []
    visibility: Literal["friends", "public"] = "friends"
    photo_w: Optional[int] = Field(None, ge=1, le=20000)  # JSON posts only: the size the app knows; uploads are measured
    photo_h: Optional[int] = Field(None, ge=1, le=20000)


class TagsEdit(BaseModel):
    user_id: str
    tagged: list[FitTag]


class UserRef(BaseModel):
    user_id: str


class LikeSet(BaseModel):
    user_id: str
    liked: bool


class CommentCreate(BaseModel):
    user_id: str
    text: str = Field(..., min_length=1, max_length=280)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user(uid: str) -> dict:
    return store.get("users", uid) or {"id": uid, "display_name": uid}


def _author(uid: str) -> dict:
    u = _user(uid)
    return {"id": u.get("id", uid), "display_name": u.get("display_name") or uid}


PREVIEW_COMMENTS = 2  # newest comments embedded in a post view; the rest come from GET .../comments


def _view(post: dict, viewer_id: str) -> dict:
    likes = post.get("likes") or []
    comments = post.get("comments") or []
    authors: dict = {}
    return {"photo_w": None, "photo_h": None, **post, "author": _author(post["user_id"]),
            "like_count": len(likes), "liked_by_me": viewer_id in likes,
            "comments": [_comment_view(c, authors) for c in comments[-PREVIEW_COMMENTS:]],
            "comment_count": len(comments)}


def _post(post_id: str, viewer_id: str) -> dict:
    post = store.get(COL, post_id)
    if not post:
        raise HTTPException(404, "unknown post")
    return post


def _photo_size(photo_url: str) -> tuple[Optional[int], Optional[int]]:
    """(width, height) in pixels of one of our saved /static images, as it displays; (None, None) for
    external URLs (never downloaded) or anything Pillow can't read. _save_upload already applied the EXIF
    rotation; a file it kept as-is (couldn't re-encode) may still carry it, so 90-degree tags swap w/h."""
    path = local_static_path(photo_url, DATA_DIR)
    if not path:
        return None, None
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            if im.getexif().get(0x0112) in (5, 6, 7, 8):
                w, h = h, w
        return w, h
    except Exception as e:  # noqa: BLE001
        log.warning("photo size unreadable for %s: %s", photo_url, e)
        return None, None


def _auto_tags(photo_url: str) -> list[dict]:
    """tag_fit -> FitTag dicts; [] on any failure (a post never fails because tagging did)."""
    if not photo_url.startswith(("http://", "https://")):
        return []
    try:
        return [FitTag(**t).model_dump() for t in service.tag_fit(photo_url)]  # keep category/color/... for shop_fit
    except Exception as e:  # noqa: BLE001
        log.warning("tag_fit failed for %s: %s", photo_url, e)
        return []


@router.post("/fitcheck")
async def create_post(request: Request):
    """JSON {user_id, photo_url, caption?, tagged?, visibility?} or multipart (user_id, file, caption?, tagged? as JSON)."""
    file = None
    if request.headers.get("content-type", "").startswith("multipart/"):
        form = await request.form()
        file = form.get("file")
        if not hasattr(file, "read"):
            raise HTTPException(422, "file required")
        raw = {k: form[k] for k in ("user_id", "caption", "visibility") if form.get(k)}
        try:
            raw["tagged"] = json.loads(form["tagged"]) if form.get("tagged") else []
        except ValueError:
            raise HTTPException(422, "tagged must be a JSON list")
        raw["photo_url"] = "pending"
    else:
        try:
            raw = await request.json()
        except ValueError:
            raise HTTPException(422, "expected JSON or multipart")
    try:
        req = PostCreate.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(422, json.loads(e.json()))
    photo_url = await _save_upload(file) if file else req.photo_url
    tagged = [t.model_dump() for t in req.tagged] or _auto_tags(photo_url)
    w, h = _photo_size(photo_url)
    if (w, h) == (None, None) and not file and req.photo_w and req.photo_h:
        w, h = req.photo_w, req.photo_h  # external URL: trust the app's size (both or neither)
    post = {"id": "fc_" + uuid.uuid4().hex[:12], "user_id": req.user_id, "photo_url": photo_url,
            "caption": req.caption, "tagged": tagged, "created_at": _now(), "likes": [], "comments": [],
            "visibility": req.visibility, "photo_w": w, "photo_h": h}
    store.put(COL, post["id"], post)
    _closet_hook(req.user_id, photo_url, tagged)  # Adam: the fit's pieces join the poster's closet (best effort)
    return _view(post, req.user_id)


def _closet_hook(user_id: str, photo_url: str, tagged: list[dict]) -> None:
    """Closet v2: add the posted outfit's pieces to the closet in the background; never fails the post."""
    try:
        from ..ai.closet import add_from_fit_later

        add_from_fit_later(user_id, photo_url, tagged)
    except Exception as e:  # noqa: BLE001
        log.warning("closet hook skipped: %s", e)


@router.get("/fitcheck/feed")
def feed(user_id: str, limit: int = 20, author: Optional[str] = None):
    """Everyone's posts, newest first; `author` = only that user's posts (tap a name in Inspo)."""
    posts = store.list(COL, user_id=author) if author else store.list(COL)
    posts.sort(key=lambda p: p["created_at"], reverse=True)
    return [_view(p, user_id) for p in posts[:max(1, min(limit, 100))]]


@router.get("/fitcheck/{post_id}")
def get_post(post_id: str, user_id: str):
    return _view(_post(post_id, user_id), user_id)


@router.patch("/fitcheck/{post_id}/tags")
def edit_tags(post_id: str, req: TagsEdit):
    """Owner fixes AI tags (wrong tags are always user-editable)."""
    post = _post(post_id, req.user_id)
    if post["user_id"] != req.user_id:
        raise HTTPException(403, "only the author can edit tags")
    post["tagged"] = [t.model_dump() for t in req.tagged]
    store.put(COL, post_id, post)
    return _view(post, req.user_id)


@router.delete("/fitcheck/{post_id}")
def delete_post(post_id: str, user_id: str):
    """Owner removes their post (e.g. swapping seed posts for real fits)."""
    post = _post(post_id, user_id)
    if post["user_id"] != user_id:
        raise HTTPException(403, "only the author can delete a post")
    store.delete(COL, post_id)
    return {"post_id": post_id, "deleted": True}


@router.get("/fitcheck/{post_id}/shop")
def shop(post_id: str, user_id: str, grouped: bool = False):
    """Products for the post's tags, ranked against the viewer's closet (ai.service.shop_fit), kept to the
    viewer's shop_for department (+ unisex/unknown, e.g. live search results).
    `grouped=true`: one group per tagged piece, in post order, `[{tag: {label, category, color, box,
    product_id}, products: [card...]}]` (up to 6 per piece; a piece with no match keeps `products: []`)."""
    tagged = _post(post_id, user_id).get("tagged") or []
    shop_for = (store.get("users", user_id) or {}).get("shop_for")

    def keep(p: dict) -> bool:  # runs on the whole catalog: products already carry their stored department
        return _dept_ok(p, shop_for)

    if grouped:
        return service.shop_fit_grouped(user_id, tagged, keep=keep)
    return service.shop_fit(user_id, tagged, keep=keep)


@router.post("/fitcheck/{post_id}/like")
def like(post_id: str, req: UserRef):
    """Toggle (kept for old builds). New clients use PUT: it's safe to retry."""
    post = _post(post_id, req.user_id)
    likes = post.setdefault("likes", [])
    liked = req.user_id not in likes
    if liked:
        likes.append(req.user_id)
    else:
        likes.remove(req.user_id)
    store.put(COL, post_id, post)
    return {"post_id": post_id, "liked": liked, "like_count": len(likes)}


@router.put("/fitcheck/{post_id}/like")
def set_like(post_id: str, req: LikeSet):
    """Idempotent like: set {liked: true|false} for user_id. Sending the same state again changes nothing,
    so an optimistic UI can retry or queue it (sprint-3 3.3)."""
    post = _post(post_id, req.user_id)
    likes = post.get("likes") or []
    if req.liked != (req.user_id in likes):
        post["likes"] = likes + [req.user_id] if req.liked else [u for u in likes if u != req.user_id]
        store.put(COL, post_id, post)
    return {"post_id": post_id, "liked": req.liked, "like_count": len(post.get("likes") or [])}


def _comment_view(c: dict, authors: dict) -> dict:
    uid = c.get("user_id") or ""
    if uid not in authors:
        authors[uid] = _author(uid)
    return {"id": c.get("id"), "user_id": uid, "author": authors[uid], "text": c.get("text", ""),
            "created_at": c.get("created_at")}


@router.get("/fitcheck/{post_id}/comments")
def list_comments(post_id: str, user_id: str, limit: int = 20, before: Optional[str] = None):
    """One page of comments, oldest -> newest (a chat-style sheet shows the newest at the bottom).
    No `before`: the newest `limit` comments. `before=<comment id>`: the `limit` comments just older than it.
    `next_before` is the cursor for the next (older) page, null when there are no older comments."""
    comments = _post(post_id, user_id).get("comments") or []
    end = len(comments)
    if before is not None:
        end = next((i for i, c in enumerate(comments) if c.get("id") == before), -1)
        if end < 0:
            raise HTTPException(422, "unknown comment id in before")
    start = max(0, end - max(1, min(limit, 100)))
    authors: dict = {}
    page = [_comment_view(c, authors) for c in comments[start:end]]
    return {"post_id": post_id, "comments": page, "next_before": page[0]["id"] if start > 0 and page else None,
            "comment_count": len(comments)}


@router.post("/fitcheck/{post_id}/comments")
def comment(post_id: str, req: CommentCreate):
    post = _post(post_id, req.user_id)
    text = req.text.strip()
    if not text:
        raise HTTPException(422, "empty comment")
    c = {"id": "c_" + uuid.uuid4().hex[:10], "user_id": req.user_id, "text": text, "created_at": _now()}
    post.setdefault("comments", []).append(c)
    store.put(COL, post_id, post)
    return {**c, "author": _author(req.user_id), "comment_count": len(post["comments"])}
