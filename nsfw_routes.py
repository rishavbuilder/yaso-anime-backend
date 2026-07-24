# nsfw_routes.py — All NSFW endpoints isolated here
# Mounted as sub-router in anime_scraper.py

import re
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

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
    first = streams[0]
    return {
        "status": "success",
        "anime": detail.get("title", slug),
        "episode": episode,
        "master_url": None,
        "embed_url": first.get("url", ""),
        "embed_referer": first.get("referer", ""),
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

        upstream_ct = resp.headers.get("Content-Type", "text/html")
        if "video/" in url.lower() or "video/" in upstream_ct:
            media_type = upstream_ct if "video/" in upstream_ct else "video/mp4"
        elif ".m3u8" in url.lower():
            media_type = "application/vnd.apple.mpegurl"
        else:
            media_type = "text/html"

        return Response(content=content, media_type=media_type, headers={
            "Access-Control-Allow-Origin": "*",
            "X-Frame-Options": "ALLOWALL",
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail="NSFW proxy error")


# ──────────────────────────────────────────────
# NSFW Video Proxy (stream video binary with Range support)
# ──────────────────────────────────────────────

@router.get("/nsfw-video-proxy")
async def nsfw_video_proxy(url: str, referer: str = ""):
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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": referer if referer else f"{parsed.scheme}://{parsed.netloc}/",
        }

        import requests as req_lib
        req_headers = dict(headers)
        r = req_lib.get(url, headers=req_headers, timeout=30, stream=True)

        if r.status_code not in (200, 206):
            raise HTTPException(status_code=r.status_code, detail="Upstream error")

        content_type = r.headers.get("Content-Type", "video/mp4")
        content_length = r.headers.get("Content-Length")
        content_range = r.headers.get("Content-Range")
        accept_ranges = r.headers.get("Accept-Ranges", "bytes")

        resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Range",
            "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges",
            "Content-Type": content_type,
            "Accept-Ranges": accept_ranges,
        }
        if content_length:
            resp_headers["Content-Length"] = content_length
        if content_range:
            resp_headers["Content-Range"] = content_range

        def stream_chunks():
            try:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            finally:
                r.close()

        status_code = 206 if r.status_code == 206 else 200
        return StreamingResponse(stream_chunks(), status_code=status_code, headers=resp_headers)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail="NSFW video proxy error")
