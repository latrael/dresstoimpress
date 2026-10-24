"""Fit Check (OOTD feed): /fitcheck posts, feed, tags, likes, comments, shop-this-fit (Nabil).

Collection fitcheck_posts: {id, user_id, photo_url, caption, tagged: [FitTag], created_at, likes: [user_id],
comments: [{id, user_id, text, created_at}], visibility: "friends" | "public"}.
Privacy: a viewer sees their own posts, friends' posts (either side of `friends`), and public ones;
a viewer with no friends list sees everything (demo). Hidden posts 404 so ids don't leak.
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
from ..store import store

log = logging.getLogger(__name__)
router = APIRouter(tags=["fitcheck"])
COL = "fitcheck_posts"


class PostCreate(BaseModel):
    user_id: str
    photo_url: str
    caption: str = Field("", max_length=500)
    tagged: list[FitTag] = []
    visibility: Literal["friends", "public"] = "friends"


class TagsEdit(BaseModel):
    user_id: str
    tagged: list[FitTag]


class UserRef(BaseModel):
    user_id: str


class CommentCreate(BaseModel):
    user_id: str
    text: str = Field(..., min_length=1, max_length=280)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user(uid: str) -> dict:
    return store.get("users", uid) or {"id": uid, "display_name": uid}


def _can_see(viewer: dict, post: dict) -> bool:
    author = post["user_id"]
    if post.get("visibility") == "public" or author == viewer["id"] or not viewer.get("friends"):
        return True
    return author in viewer["friends"] or viewer["id"] in (_user(author).get("friends") or [])


def _view(post: dict, viewer_id: str) -> dict:
    author = _user(post["user_id"])
    likes = post.get("likes") or []
    return {**post, "author": {"id": author["id"], "display_name": author.get("display_name", author["id"])},
            "like_count": len(likes), "liked_by_me": viewer_id in likes,
            "comment_count": len(post.get("comments") or [])}


def _post(post_id: str, viewer_id: str) -> dict:
    post = store.get(COL, post_id)
    if not post or not _can_see(_user(viewer_id), post):
        raise HTTPException(404, "unknown post")
    return post


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
    post = {"id": "fc_" + uuid.uuid4().hex[:12], "user_id": req.user_id, "photo_url": photo_url,
            "caption": req.caption, "tagged": tagged, "created_at": _now(), "likes": [], "comments": [],
            "visibility": req.visibility}
    store.put(COL, post["id"], post)
    return _view(post, req.user_id)


@router.get("/fitcheck/feed")
def feed(user_id: str, limit: int = 20):
    viewer = _user(user_id)
    posts = [p for p in store.list(COL) if _can_see(viewer, p)]
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
def shop(post_id: str, user_id: str):
    """Products for the post's tags, ranked against the viewer's closet (ai.service.shop_fit as-is)."""
    return service.shop_fit(user_id, _post(post_id, user_id).get("tagged") or [])


@router.post("/fitcheck/{post_id}/like")
def like(post_id: str, req: UserRef):
    post = _post(post_id, req.user_id)
    likes = post.setdefault("likes", [])
    liked = req.user_id not in likes
    if liked:
        likes.append(req.user_id)
    else:
        likes.remove(req.user_id)
    store.put(COL, post_id, post)
    return {"post_id": post_id, "liked": liked, "like_count": len(likes)}


@router.post("/fitcheck/{post_id}/comments")
def comment(post_id: str, req: CommentCreate):
    post = _post(post_id, req.user_id)
    text = req.text.strip()
    if not text:
        raise HTTPException(422, "empty comment")
    c = {"id": "c_" + uuid.uuid4().hex[:10], "user_id": req.user_id, "text": text, "created_at": _now()}
    post.setdefault("comments", []).append(c)
    store.put(COL, post_id, post)
    return {**c, "comment_count": len(post["comments"])}
