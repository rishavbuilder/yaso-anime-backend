# nsfw_routes.py — All NSFW endpoints isolated here
# Mounted as sub-router in anime_scraper.py

import re
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

import nsfw_scraper

router = APIRouter()


# ──────────────────────────────────────────────
# NSFW Homepage / Browse
# ──────────────────────────────────────────────

@router.get("/api/nsfw/homepage")
async def nsfw_homepage():
    data = nsfw_scraper.nsfw_homepage()
    return {"status": "success", **data}


@router.get("/api/nsfw/trending")
async def nsfw_trending():
    return nsfw_scraper.nsfw_trending()


@router.get("/api/nsfw/recent")
async def nsfw_recent():
    return nsfw_scraper.nsfw_recent()


@router.get("/api/nsfw/new-release")
async def nsfw_new_release():
    return nsfw_scraper.nsfw_new_release()


@router.get("/api/nsfw/new-added")
async def nsfw_new_added():
    return nsfw_scraper.nsfw_new_added()


@router.get("/api/nsfw/completed")
async def nsfw_completed():
    return nsfw_scraper.nsfw_completed()


@router.get("/api/nsfw/top")
async def nsfw_top():
    return nsfw_scraper.nsfw_top()


# ──────────────────────────────────────────────
# NSFW Search
# ──────────────────────────────────────────────

@router.get("/api/nsfw/search")
async def nsfw_search(q: str = "", page: int = 1):
    return nsfw_scraper.nsfw_search(q, page)


# ──────────────────────────────────────────────
# NSFW Detail & Stream
# ──────────────────────────────────────────────

@router.get("/api/nsfw/detail")
async def nsfw_detail(slug: str):
    result = nsfw_scraper.nsfw_detail(slug)
    if not result:
        raise HTTPException(status_code=404, detail="NSFW content not found")
    return result


class StreamRequest:
    def __init__(self, slug: str = "", episode: int = 1):
        self.slug = slug
        self.episode = episode


@router.post("/api/nsfw/stream")
async def nsfw_stream(body: dict):
    slug = body.get("slug", "")
    episode = body.get("episode", 1)
    detail = nsfw_scraper.nsfw_detail(slug) or {}
    streams = detail.get("stream_urls", [])
    if not streams:
        raise HTTPException(status_code=404, detail="NSFW stream not found")
    return {
        "status": "success",
        "anime": detail.get("title", slug),
        "episode": episode,
        "master_url": None,
        "embed_url": streams[0].get("url", ""),
        "servers": streams,
        "source": detail.get("source", "nsfw"),
        "meta": {"episodes": 1, "anilist": None, "relations": []},
    }


# ──────────────────────────────────────────────
# NSFW Proxy (bypass X-Frame-Options)
# ──────────────────────────────────────────────

@router.get("/nsfw-proxy")
async def nsfw_proxy(url: str):
    if url.startswith("//"):
        url = "https:" + url
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(status_code=400, detail="Invalid URL")
        host = parsed.hostname or ""
        if host.startswith("10.") or host.startswith("192.168."):
            raise HTTPException(status_code=400, detail="Invalid URL")
        if host.startswith("172.") and 16 <= int(host.split(".")[1] or 0) <= 31:
            raise HTTPException(status_code=400, detail="Invalid URL")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        resp = nsfw_scraper.http_get(url, headers={
            **nsfw_scraper.HEADERS,
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }, timeout=15)
        content = resp.text

        def fix_rel(m):
            prefix = m.group(1)
            path = m.group(2)
            if path.startswith(("http://", "https://", "//")):
                return m.group(0)
            return f'{prefix}{base}/{path.lstrip("/")}'

        content = re.sub(r'((?:src|href|action)=["\'])((?!https?://|//)[^"\']+)', fix_rel, content)
        content = re.sub(r'((?:poster|source|file)\s*[:=]\s*["\'])((?!https?://|//)[^"\']+)', fix_rel, content)

        return Response(content=content, media_type="text/html", headers={
            "Access-Control-Allow-Origin": "*",
            "X-Frame-Options": "ALLOWALL",
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail="NSFW proxy error")
