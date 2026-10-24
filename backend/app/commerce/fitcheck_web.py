"""Public Fit Check page for the hackathon table: scan a QR, upload an outfit, it lands in the feed (Nabil).

Served WITHOUT X-DTI-Key (main.py adds "/fit" to OPEN_PREFIXES), so everything here guards itself:
- every route needs ?code=FITCHECK_EVENT_CODE (env, read per request); unset -> 404, so it's off by default
- image only (content-type + magic bytes), 8 MB, caption <= 140, name <= 30, HTML stripped, output escaped
- per-IP rate limit (FITCHECK_RATE posts per FITCHECK_RATE_WINDOW s) and a total guest-post cap
- guests get a g_<8 hex> id in a cookie and a minimal user doc; posts are public
- the wall returns display names only, never user ids
Creation reuses fitcheck.py (_save_upload, _auto_tags, COL); fitcheck.py is unchanged.
"""
from __future__ import annotations

import hmac
import html
import io
import os
import re
import secrets
import threading
import time
import uuid
from collections import deque
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, UploadFile

from ..ai.router import _save_upload
from ..store import store
from .fitcheck import COL, _auto_tags, _now

router = APIRouter(tags=["fitcheck-web"])

MAX_BYTES = 8 * 1024 * 1024
MAX_CAPTION, MAX_NAME = 140, 30
COOKIE = "dti_guest"
GUEST_RE = re.compile(r"^g_[0-9a-f]{8}$")
TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"}
HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1"}
SEC_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
               "X-Frame-Options": "DENY"}
CSP = ("default-src 'none'; img-src * data: blob:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

_hits: dict[str, deque] = {}
_lock = threading.Lock()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _gate(code: str) -> str:
    want = os.getenv("FITCHECK_EVENT_CODE", "")
    if not want:
        raise HTTPException(404, "disabled")
    if not hmac.compare_digest(code.encode(), want.encode()):
        raise HTTPException(403, "wrong event code")
    return want


def _ip(request: Request) -> str:
    ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0]
    return ip.strip() or (request.client.host if request.client else "?")


def _rate_ok(ip: str) -> bool:
    limit, window, now = _env_int("FITCHECK_RATE", 5), _env_int("FITCHECK_RATE_WINDOW", 600), time.time()
    with _lock:
        q = _hits.setdefault(ip, deque())
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def _clean(s, limit: int, field: str) -> str:
    s = re.sub(r"<[^>]*>", "", str(s or ""))
    s = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", s)).strip()
    if len(s) > limit:
        raise HTTPException(422, f"{field} over {limit} characters")
    return s


def _sniff(data: bytes) -> str | None:
    """Real image type from magic bytes (never trust the client's content-type alone)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in HEIF_BRANDS:
        return "image/heic"
    return None


def _tags(post: dict) -> list[dict]:
    return [{"label": t.get("label", ""), "color": t.get("color")} for t in post.get("tagged") or [] if t.get("label")]


def _name(uid: str) -> str:
    return (store.get("users", uid) or {}).get("display_name") or "someone"  # never fall back to the id


@router.get("/fit", response_class=HTMLResponse)
def page(request: Request, code: str = ""):
    _gate(code)
    gid = request.cookies.get(COOKIE, "")
    name = _name(gid) if GUEST_RE.match(gid) and store.get("users", gid) else ""
    body = PAGE.replace("{{NAME}}", html.escape(name, quote=True))
    return HTMLResponse(body, headers={**SEC_HEADERS, "Content-Security-Policy": CSP})


@router.post("/fit/post")
async def post(request: Request, code: str = ""):
    _gate(code)
    if int(request.headers.get("content-length") or 0) > MAX_BYTES + 64 * 1024:
        raise HTTPException(413, "image over 8 MB")
    if not request.headers.get("content-type", "").startswith("multipart/"):
        raise HTTPException(422, "expected multipart form")
    if not _rate_ok(_ip(request)):
        raise HTTPException(429, "slow down: max 5 posts per 10 minutes")
    if sum(1 for p in store.list(COL) if str(p.get("user_id", "")).startswith("g_")) >= _env_int(
            "FITCHECK_GUEST_MAX", 200):
        raise HTTPException(429, "the wall is full, thanks for playing")
    form = await request.form(max_files=1, max_fields=4)
    file = form.get("file")
    if not hasattr(file, "read"):
        raise HTTPException(422, "photo required")
    name = _clean(form.get("name"), MAX_NAME, "name") or "Guest"
    caption = _clean(form.get("caption"), MAX_CAPTION, "caption")
    if (file.content_type or "").lower() not in TYPES:
        raise HTTPException(415, "photos only (jpeg, png, webp, heic)")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "image over 8 MB")
    ctype = _sniff(data)
    if not ctype:
        raise HTTPException(415, "that file isn't a photo")
    photo_url = await _save_upload(UploadFile(io.BytesIO(data), headers=Headers({"content-type": ctype})))
    gid = request.cookies.get(COOKIE, "")
    if not GUEST_RE.match(gid):
        gid = "g_" + secrets.token_hex(4)
    store.put("users", gid, {**(store.get("users", gid) or {"friends": []}), "id": gid, "display_name": name})
    tagged = await run_in_threadpool(_auto_tags, photo_url)  # [] on any failure; Claude budget cap lives in llm
    p = {"id": "fc_" + uuid.uuid4().hex[:12], "user_id": gid, "photo_url": photo_url, "caption": caption,
         "tagged": tagged, "created_at": _now(), "likes": [], "comments": [], "visibility": "public"}
    store.put(COL, p["id"], p)
    r = JSONResponse({"post_id": p["id"], "photo_url": photo_url, "caption": caption, "author_name": name,
                      "tagged": _tags(p)}, headers=SEC_HEADERS)
    r.set_cookie(COOKIE, gid, max_age=30 * 86400, httponly=True, samesite="lax", path="/fit",
                 secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https")
    return r


@router.get("/fit/wall")
def wall(code: str = "", limit: int = 12):
    _gate(code)
    posts = [p for p in store.list(COL) if p.get("visibility") == "public"
             and str(p.get("photo_url", "")).startswith(("http://", "https://"))]
    posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    out = [{"id": p["id"], "photo_url": p["photo_url"], "caption": p.get("caption", ""),
            "author_name": _name(p.get("user_id", "")), "tags": _tags(p), "created_at": p.get("created_at")}
           for p in posts[:max(1, min(limit, 50))]]
    return JSONResponse(out, headers=SEC_HEADERS)


@router.get("/fit/qr", response_class=HTMLResponse)
def qr(code: str = ""):
    """No QR library in requirements.txt, so: the URL in big text to paste into any QR generator."""
    want = _gate(code)
    url = html.escape(f"{os.getenv('PUBLIC_BASE', 'http://localhost:8000').rstrip('/')}/fit?code={quote(want)}")
    return HTMLResponse(QR_PAGE.replace("{{URL}}", url), headers={**SEC_HEADERS, "Content-Security-Policy": CSP})


QR_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Fit Check QR · dresstoimpress</title>
<style>body{font:16px system-ui,-apple-system,sans-serif;margin:0;padding:32px 16px;text-align:center;
background:#fff;color:#111}h1{font-size:40px;margin:0 0 8px}p{color:#555}
.u{font:700 clamp(18px,4vw,34px) ui-monospace,Menlo,monospace;word-break:break-all;border:3px solid #111;
border-radius:16px;padding:24px;margin:24px auto;max-width:900px}</style></head><body>
<h1>Fit Check 📸</h1><p>Scan, post your outfit, see it on our table's feed. No app needed.</p>
<div class="u">{{URL}}</div>
<p>No QR library is installed on this server. Paste the URL above into any QR generator and print it.</p>
</body></html>"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark"><title>Fit Check · dresstoimpress</title>
<style>
:root{--bg:#f6f4f1;--card:#fff;--fg:#141414;--mute:#6b6b6b;--line:#e4e0da;--acc:#ff3d6e;--acc2:#7a3dff;--chip:#f1edf9}
@media (prefers-color-scheme:dark){:root{--bg:#0e0e10;--card:#18181b;--fg:#f4f4f5;--mute:#a1a1aa;--line:#2a2a2f;
--chip:#26203a}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 -apple-system,BlinkMacSystemFont,system-ui,
"Segoe UI",Roboto,sans-serif;padding:max(16px,env(safe-area-inset-top)) 16px 48px}
main{max-width:520px;margin:0 auto}
h1{font-size:30px;letter-spacing:-.02em;margin:8px 0 2px}h1 span{background:linear-gradient(90deg,var(--acc),
var(--acc2));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{color:var(--mute);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:16px;margin-bottom:20px}
label.f{display:block;font-size:13px;font-weight:600;color:var(--mute);margin:12px 0 6px}
input[type=text]{width:100%;font-size:16px;padding:12px 14px;border-radius:12px;border:1px solid var(--line);
background:var(--bg);color:var(--fg);outline:none}input[type=text]:focus{border-color:var(--acc2)}
.pick{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;min-height:180px;
border:2px dashed var(--line);border-radius:16px;cursor:pointer;text-align:center;font-weight:600;overflow:hidden;
position:relative}.pick small{color:var(--mute);font-weight:400}
.pick img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.pick input{position:absolute;width:1px;height:1px;opacity:0}
button{width:100%;font-weight:600;font-size:17px;font-family:inherit;padding:15px;border:0;border-radius:14px;margin-top:16px;
color:#fff;background:linear-gradient(90deg,var(--acc),var(--acc2));cursor:pointer}
button:disabled{opacity:.6}button.ghost{background:transparent;color:var(--fg);border:1px solid var(--line)}
.err{color:var(--acc);font-size:14px;min-height:1em;margin:10px 0 0}
.res img{width:100%;border-radius:14px;display:block;max-height:70vh;object-fit:cover}
.res h2{font-size:18px;margin:14px 0 8px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.chip{background:var(--chip);border-radius:999px;padding:4px 10px;font-size:13px;white-space:nowrap;max-width:100%;
overflow:hidden;text-overflow:ellipsis}
h3{font-size:20px;margin:6px 0 10px;display:flex;align-items:center;gap:8px}
h3 i{width:8px;height:8px;border-radius:50%;background:var(--acc);display:inline-block;animation:p 1.6s infinite}
@keyframes p{50%{opacity:.25}}
.wall{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.tile img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;background:var(--line)}
.tile div{padding:8px 10px}.tile b{font-size:14px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tile .chip{font-size:11px;padding:3px 8px}.empty{color:var(--mute);grid-column:1/-1}
[hidden]{display:none!important}
</style></head><body><main>
<h1>Fit Check <span>·</span> dresstoimpress</h1>
<p class="sub">Snap your outfit. Our AI tags every piece and drops it on the feed at our table.</p>
<form id="f" class="card" novalidate>
<label class="f" for="name">Your name</label>
<input type="text" id="name" name="name" maxlength="30" autocomplete="nickname" placeholder="e.g. Sam" value="{{NAME}}">
<label class="f">Your fit</label>
<label class="pick" id="pick"><span>📸 Take / choose photo</span><small>JPEG, PNG, WebP or HEIC · up to 8 MB</small>
<input type="file" id="file" name="file" accept="image/*"><img id="prev" alt="" hidden></label>
<label class="f" for="cap">Caption (optional)</label>
<input type="text" id="cap" name="caption" maxlength="140" placeholder="hackathon drip">
<button id="go" type="submit">Post</button><p class="err" id="err" role="alert"></p>
</form>
<section id="res" class="card res" hidden>
<img id="rimg" alt="Your outfit"><h2>AI spotted</h2><div class="chips" id="rtags"></div>
<p>You're on the Fit Check feed at our table 👀</p>
<button class="ghost" id="again" type="button">Post another</button>
</section>
<h3><i></i>Live wall</h3><div class="wall" id="wall"><p class="empty">Loading…</p></div>
</main><script>
(function(){
var Q=location.search,$=function(i){return document.getElementById(i)},f=$('f'),go=$('go'),err=$('err');
function chip(t){var s=document.createElement('span');s.className='chip';
s.textContent=t.color?t.label+' \\u00b7 '+t.color:t.label;return s}
function msg(d){return typeof d==='string'?d:(Array.isArray(d)&&d[0]&&d[0].msg)||'Something went wrong'}
$('file').addEventListener('change',function(){var x=this.files[0],p=$('prev');
if(x){p.src=URL.createObjectURL(x);p.hidden=false}else p.hidden=true});
f.addEventListener('submit',function(e){e.preventDefault();err.textContent='';
if(!$('file').files[0]){err.textContent='Pick a photo first';return}
go.disabled=true;go.textContent='Tagging your fit\\u2026';
fetch('/fit/post'+Q,{method:'POST',body:new FormData(f),credentials:'same-origin'})
.then(function(r){return r.json().catch(function(){return{}}).then(function(j){if(!r.ok)throw new Error(msg(j.detail));return j})})
.then(function(j){$('rimg').src=j.photo_url;var c=$('rtags');c.textContent='';
(j.tagged.length?j.tagged:[{label:'no tags this time'}]).forEach(function(t){c.appendChild(chip(t))});
f.hidden=true;$('res').hidden=false;window.scrollTo(0,0);wall()})
.catch(function(x){err.textContent=x.message||'Upload failed, try again'})
.then(function(){go.disabled=false;go.textContent='Post'})});
$('again').addEventListener('click',function(){var n=$('name').value;f.reset();$('name').value=n;$('prev').hidden=true;
$('res').hidden=true;f.hidden=false});
function wall(){if(document.hidden)return;fetch('/fit/wall'+Q+'&limit=12').then(function(r){return r.ok?r.json():[]})
.then(function(ps){var w=$('wall');w.textContent='';
if(!ps.length){var e=document.createElement('p');e.className='empty';e.textContent='No fits yet. Be the first!';w.appendChild(e)}
ps.forEach(function(p){var t=document.createElement('div'),i=document.createElement('img'),d=document.createElement('div'),
b=document.createElement('b'),c=document.createElement('div');t.className='tile';i.src=p.photo_url;i.alt='';
i.loading='lazy';b.textContent=p.author_name;c.className='chips';p.tags.slice(0,2).forEach(function(x){c.appendChild(chip(x))});
d.appendChild(b);d.appendChild(c);t.appendChild(i);t.appendChild(d);w.appendChild(t)})}).catch(function(){})}
wall();setInterval(wall,15000);
})();
</script></body></html>"""
