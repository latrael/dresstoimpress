"""Inspo additions (Adam, Oct 25): emoji reactions and "find similar look". Thin routes over fitcheck_posts.

Reactions generalize likes: one reaction per user, from REACTIONS. Stored as `reactions: {emoji: [user_id]}`
next to the old `likes` list, which stays the source of truth for *who* reacted, so old builds (POST/PUT
/like) keep working: a like without a reaction counts as LEGACY ("😍"), an unlike removes the reaction.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..store import store

router = APIRouter(tags=["fitcheck"])
COL = "fitcheck_posts"
REACTIONS = ["🔥", "😍", "👀", "💯"]
LEGACY = "😍"


def reaction_map(post: dict) -> dict[str, list[str]]:
    likes = list(post.get("likes") or [])
    members = set(likes)
    out: dict[str, list[str]] = {}
    placed: set[str] = set()
    for emoji, users in (post.get("reactions") or {}).items():
        if emoji not in REACTIONS:
            continue
        for u in users or []:
            if u in members and u not in placed:
                out.setdefault(emoji, []).append(u)
                placed.add(u)
    for u in likes:
        if u not in placed:
            out.setdefault(LEGACY, []).append(u)
            placed.add(u)
    return out


def set_reaction(post: dict, user_id: str, emoji: Optional[str]) -> dict:
    """Mutates and returns post: the user's reaction becomes `emoji` (None removes it)."""
    r = {e: [u for u in us if u != user_id] for e, us in reaction_map(post).items()}
    if emoji:
        r.setdefault(emoji, []).append(user_id)
    post["reactions"] = {e: us for e, us in r.items() if us}
    likes = [u for u in (post.get("likes") or []) if u != user_id]
    if emoji:
        likes.append(user_id)
    post["likes"] = likes
    return post


def reaction_view(post: dict, viewer_id: str) -> dict:
    r = reaction_map(post)
    mine = next((e for e, us in r.items() if viewer_id in us), None)
    return {"reactions": {e: len(r[e]) for e in REACTIONS if r.get(e)}, "my_reaction": mine}


class ReactionSet(BaseModel):
    user_id: str
    emoji: Optional[str] = None


@router.put("/fitcheck/{post_id}/reaction")
def put_reaction(post_id: str, req: ReactionSet):
    """Idempotent: set the user's reaction to `emoji` (one of REACTIONS) or clear it with null."""
    if req.emoji is not None and req.emoji not in REACTIONS:
        raise HTTPException(422, f"emoji must be one of {REACTIONS}")
    post = store.get(COL, post_id)
    if not post:
        raise HTTPException(404, "unknown post")
    set_reaction(post, req.user_id, req.emoji)
    store.put(COL, post_id, post)
    likes = post.get("likes") or []
    return {"post_id": post_id, **reaction_view(post, req.user_id), "like_count": len(likes),
            "liked": req.user_id in likes}


@router.get("/fitcheck/{post_id}/similar")
def similar(post_id: str, user_id: str):
    """Find similar look: one group per tagged piece, in post order: `[{tag, closet: [ClosetItem],
    products: [card]}]`, closet = the viewer's own similar pieces (rules, free), products = shop_fit_grouped
    in the viewer's shop_for department."""
    from ..ai.similar_look import similar_look
    from .router import _dept_ok

    post = store.get(COL, post_id)
    if not post:
        raise HTTPException(404, "unknown post")
    shop_for = (store.get("users", user_id) or {}).get("shop_for")
    return similar_look(user_id, post.get("tagged") or [], keep=lambda p: _dept_ok(p, shop_for))
