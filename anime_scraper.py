# anime_scraper.py — Full Rewrite
# Sources: Anikoto (search, stream, homepage), AniList (detail, browse)

import os, re, time, asyncio, logging
from urllib.parse import urlparse, quote
from typing import Optional

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nsfw_routes import router as nsfw_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("anime")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

DIR = os.path.dirname(os.path.abspath(__file__))
ANIKOTO_DOMAIN = "https://anikoto.cz"
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

# ──────────────────────────────────────────────
# HTTP Session (shared with retries)
# ──────────────────────────────────────────────

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=2, pool_connections=10, pool_maxsize=20)
session.mount("https://", adapter)
session.mount("http://", adapter)


def http_get(url, **kwargs):
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", TIMEOUT)
    return session.get(url, **kwargs)


def http_post(url, **kwargs):
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", TIMEOUT)
    return session.post(url, **kwargs)


# ──────────────────────────────────────────────
# TTL Cache
# ──────────────────────────────────────────────

_cache = {}


def cache_get(key):
    if key in _cache:
        data, expiry = _cache[key]
        if time.time() < expiry:
            return data
        del _cache[key]
    return None


def cache_set(key, data, ttl):
    _cache[key] = (data, time.time() + ttl)


def cached(ttl):
    """Decorator: cache function result for `ttl` seconds."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            cache_key = f"{fn.__name__}:{args}:{kwargs}"
            result = cache_get(cache_key)
            if result is not None:
                return result
            result = fn(*args, **kwargs)
            if result is not None:
                cache_set(cache_key, result, ttl)
            return result
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


# ──────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────

class StreamRequest(BaseModel):
    title: str = ""
    episode: int = Field(default=1, ge=1)
    source: str = "auto"
    slug: str = ""


# ──────────────────────────────────────────────
# AniList API (detail + browse only)
# ──────────────────────────────────────────────

ANILIST_DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english native }
    description(asHtml: false)
    coverImage { large medium color }
    bannerImage
    genres
    status
    episodes
    duration
    averageScore
    popularity
    season
    seasonYear
    format
    type
    source
    countryOfOrigin
    isAdult
    synonyms
    nextAiringEpisode { episode airingAt }
    relations {
      edges {
        node { id title { romaji english } format coverImage { medium } }
        relationType
      }
    }
    streamingEpisodes { title thumbnail url site }
    staff {
      edges { node { name { full } } role }
    }
    studios { nodes { name } }
    trailer { id site thumbnail }
  }
}
"""

ANILIST_SEARCH_QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    title { romaji english native }
    coverImage { large medium }
    format
    episodes
    status
    averageScore
    isAdult
  }
}
"""

ANILIST_BROWSE_QUERY = """
query ($page: Int, $perPage: Int, $genre: String, $format: String, $sort: [MediaSort]) {
  Page(page: $page, perPage: $perPage) {
    media(type: ANIME, genre: $genre, format: $format, sort: $sort) {
      id
      title { romaji english }
      coverImage { large color }
      bannerImage
      format
      episodes
      averageScore
      genres
      status
      description(asHtml: false)
      season
      seasonYear
      duration
      isAdult
    }
    pageInfo { total lastPage hasNextPage }
  }
}
"""

ANILIST_SEARCH_LIST_QUERY = """
query ($search: String, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
      id
      title { romaji english }
      coverImage { medium color }
      format
      episodes
      status
      averageScore
      isAdult
    }
  }
}
"""


def _anilist_gql(query, variables):
    try:
        resp = http_post("https://graphql.anilist.co",
                         json={"query": query, "variables": variables},
                         headers={"Content-Type": "application/json"})
        return resp.json().get("data") or {}
    except Exception as e:
        log.error(f"AniList GQL error: {e}")
        return {}


def _parse_media(m):
    """Single consistent media parser for all AniList data."""
    na = m.get("nextAiringEpisode")
    return {
        "id": m["id"],
        "title": m["title"].get("english") or m["title"].get("romaji") or "",
        "title_romaji": m["title"].get("romaji", ""),
        "cover": (m.get("coverImage") or {}).get("large"),
        "banner": m.get("bannerImage"),
        "format": m.get("format"),
        "episodes": m.get("episodes"),
        "score": m.get("averageScore"),
        "genres": m.get("genres", []),
        "status": m.get("status"),
        "description": (m.get("description") or "").strip(),
        "season": m.get("season"),
        "season_year": m.get("seasonYear"),
        "duration": m.get("duration"),
        "next_airing": {"episode": na["episode"], "airingAt": na["airingAt"]} if na else None,
        "airing_at": na["airingAt"] if na else None,
        "is_adult": m.get("isAdult", False),
        "source": "anilist",
    }


def _parse_anilist_detail(media):
    """Full detail parser for /anime/{id}."""
    desc = (media.get("description") or "").strip()
    desc = re.sub(r'<[^>]+>', '', desc)
    desc = re.sub(r'\n{3,}', '\n\n', desc)
    relations = []
    for edge in (media.get("relations") or {}).get("edges", []):
        node = edge.get("node", {})
        relations.append({
            "id": node.get("id"),
            "title": node.get("title", {}).get("english") or node.get("title", {}).get("romaji"),
            "format": node.get("format"),
            "relation": edge.get("relationType"),
            "cover": (node.get("coverImage") or {}).get("medium"),
        })
    staff = []
    for edge in (media.get("staff") or {}).get("edges", [])[:10]:
        node = edge.get("node", {})
        staff.append({"name": node.get("name", {}).get("full"), "role": edge.get("role")})
    studios = [s.get("name") for s in (media.get("studios") or {}).get("nodes", [])]
    na = media.get("nextAiringEpisode")
    return {
        "id": media["id"],
        "title": media["title"].get("english") or media["title"].get("romaji") or "",
        "title_romaji": media["title"].get("romaji", ""),
        "title_native": media["title"].get("native", ""),
        "description": desc,
        "cover": (media.get("coverImage") or {}).get("large"),
        "banner": media.get("bannerImage"),
        "color": (media.get("coverImage") or {}).get("color"),
        "genres": media.get("genres", []),
        "status": media.get("status"),
        "episodes": media.get("episodes"),
        "duration": media.get("duration"),
        "score": media.get("averageScore"),
        "popularity": media.get("popularity"),
        "season": media.get("season"),
        "season_year": media.get("seasonYear"),
        "format": media.get("format"),
        "source": media.get("source"),
        "country": media.get("countryOfOrigin"),
        "is_adult": media.get("isAdult", False),
        "synonyms": media.get("synonyms", []),
        "studios": studios,
        "staff": staff,
        "relations": relations,
        "trailer": media.get("trailer"),
        "streaming_episodes": media.get("streamingEpisodes", []),
        "next_airing": {"episode": na["episode"], "airingAt": na["airingAt"]} if na else None,
    }


@cached(3600)
def anilist_detail(anime_id):
    data = _anilist_gql(ANILIST_DETAIL_QUERY, {"id": anime_id})
    media = data.get("Media")
    return _parse_anilist_detail(media) if media else None


@cached(3600)
def anilist_search(title):
    data = _anilist_gql(ANILIST_SEARCH_QUERY, {"search": title})
    media = data.get("Media")
    if media:
        return {
            "id": media["id"],
            "title": media["title"].get("english") or media["title"].get("romaji") or "",
        }
    return None


# ──────────────────────────────────────────────
# Anikoto Scraper
# ──────────────────────────────────────────────

def _extract_slug(href):
    m = re.search(r'/watch/([a-z0-9][a-z0-9-]+[a-z0-9])', href or "", re.IGNORECASE)
    return m.group(1) if m else ""


def _parse_bg_image(style_str):
    m = re.search(r"url\(['\"]?([^'\")\s]+)['\"]?\)", style_str or "")
    return m.group(1) if m else ""


def anikoto_search(title):
    """Search anikoto for an anime title, return (slug, name) or (None, None).
    Picks best match by scoring: exact/closest slug wins over OVA/movie/special variants."""
    try:
        resp = http_get(f"{ANIKOTO_DOMAIN}/search", params={"keyword": title})
        if resp.status_code != 200:
            return None, None
        slugs = re.findall(r'/watch/([a-z0-9][a-z0-9-]+[a-z0-9])', resp.text, re.IGNORECASE)
        clean = title.lower().replace(" ", "-").replace("'", "")
        clean = re.sub(r'-+', '-', clean).strip('-')

        # Words that indicate non-main entries
        skip_words = {"ova", "movie", "special", "junior-high", "no-regrets",
                       "lost-girls", "chronicle", "wings-of-freedom",
                       "crimson-bow-and-arrow", "the-last-attack"}

        seen = set()
        candidates = []
        for slug in slugs:
            if slug in seen:
                continue
            seen.add(slug)
            # Remove trailing 5-char hash suffix for comparison
            slug_clean = re.sub(r'-[a-z0-9]{5}$', '', slug)
            if not (clean in slug_clean or slug_clean in clean):
                continue

            # Score: lower = better
            score = 0
            # Penalize non-main entries
            for word in skip_words:
                if word in slug_clean:
                    score += 100
                    break
            # Prefer slug that is closest to clean title
            score += abs(len(slug_clean) - len(clean))
            # Prefer no extra parts beyond the title
            extra = slug_clean.replace(clean, "").strip("-")
            if extra:
                score += 50

            candidates.append((score, slug))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            best = candidates[0][1]
            log.info(f"Anikoto search: '{title}' -> {best} (score {candidates[0][0]})")
            return best, title

    except Exception as e:
        log.error(f"Anikoto search error: {e}")
    return None, None


def anikoto_get_stream(slug, episode_num):
    """Fetch stream data from anikoto for a specific episode."""
    try:
        resp = http_get(f"{ANIKOTO_DOMAIN}/watch/{slug}")
        if resp.status_code != 200:
            log.error(f"Anikoto watch page {resp.status_code} for slug={slug}")
            return None

        # Extract show ID
        m = re.search(r'getinfo/(\d+)', resp.text)
        if not m:
            log.error(f"Anikoto: no getinfo found for slug={slug}")
            return None
        video_id = m.group(1)

        # Extract anime name
        title_el = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', resp.text)
        anime_name = title_el.group(1).strip() if title_el else slug

        # Fetch episode list
        ep_resp = http_get(
            f"{ANIKOTO_DOMAIN}/ajax/episode/list/{video_id}",
            params={"vrf": ""},
            headers={**HEADERS, "x-requested-with": "XMLHttpRequest"}
        )
        if ep_resp.status_code != 200:
            log.error(f"Anikoto: episode list fetch failed {ep_resp.status_code}")
            return None

        soup = BeautifulSoup(ep_resp.json().get("result", ""), "html.parser")
        episodes = soup.find_all("li", {"data-html": "true"})
        data_nums = []
        for ep_li in episodes:
            a_tag = ep_li.find("a")
            if a_tag and a_tag.get("data-num", "").isdigit():
                data_nums.append(int(a_tag["data-num"]))
        total_episodes = max(data_nums) if data_nums else len(episodes)
        log.info(f"Anikoto: {total_episodes} episodes found for slug={slug}")

        if episode_num < 1 or episode_num > total_episodes:
            log.warning(f"Anikoto: episode {episode_num} out of range (1-{total_episodes})")
            return None

        # Match episode by data-num attribute
        matched_ep = None
        for ep_li in episodes:
            a_tag = ep_li.find("a")
            if a_tag and a_tag.get("data-num", "") == str(episode_num):
                matched_ep = ep_li
                break

        if not matched_ep:
            log.error(f"Anikoto: could not find episode {episode_num} by data-num")
            return None

        # Get data-ids for server list
        a = matched_ep.find("a")
        data_ids = a.get("data-ids") if a else None
        if not data_ids:
            log.error(f"Anikoto: no data-ids for episode {episode_num}")
            return None

        # Fetch server list
        srv_resp = http_get(
            f"{ANIKOTO_DOMAIN}/ajax/server/list",
            params={"servers": data_ids},
            headers={**HEADERS, "x-requested-with": "XMLHttpRequest"}
        )
        if srv_resp.status_code != 200:
            log.error(f"Anikoto: server list fetch failed {srv_resp.status_code}")
            return None

        srv_soup = BeautifulSoup(srv_resp.json().get("result", ""), "html.parser")
        servers_div = srv_soup.find_all("div", class_="type")

        servers = []
        for div in servers_div:
            srv_type = div.get("data-type", "").upper()
            for li in div.find_all("li"):
                data_link_id = li.get("data-link-id")
                srv_name = li.text.strip()
                if data_link_id:
                    servers.append({"type": srv_type, "name": srv_name, "data_link_id": data_link_id})

        # Resolve each server to get embed URLs
        all_server_urls = []
        best_master = None
        best_qualities = []
        best_embed = None

        for srv in servers:
            try:
                s_resp = http_get(
                    f"{ANIKOTO_DOMAIN}/ajax/server",
                    params={"get": srv["data_link_id"]},
                    headers={**HEADERS, "x-requested-with": "XMLHttpRequest"}
                )
                if s_resp.status_code != 200:
                    continue
                result_data = s_resp.json().get("result", {})
                embed_url = result_data.get("url", "")
                if not embed_url:
                    continue

                srv_label = f"{srv['type']} - {srv['name']}" if srv.get("type") else srv["name"]
                all_server_urls.append({"name": srv_label, "url": embed_url})

                if not best_embed:
                    best_embed = embed_url

                # Try to extract m3u8 from megaplay.buzz
                if "megaplay.buzz" in embed_url:
                    try:
                        me_resp = http_get(
                            embed_url,
                            headers={**HEADERS, "Referer": f"{ANIKOTO_DOMAIN}/"}
                        )
                        data_id_match = re.search(r'data-id="(\d+)"', me_resp.text)
                        if data_id_match:
                            src_resp = http_get(
                                f"https://megaplay.buzz/stream/getSources?id={data_id_match.group(1)}",
                                headers={"Referer": "https://megaplay.buzz/"}
                            )
                            if src_resp.status_code == 200:
                                src_json = src_resp.json()
                                sources = src_json.get("sources")
                                if sources and isinstance(sources, dict):
                                    m3u8_url = sources.get("file", "")
                                    if m3u8_url and not best_master:
                                        best_master = m3u8_url
                                        if ".m3u8" in m3u8_url:
                                            best_qualities = _get_qualities(m3u8_url)
                    except Exception as e:
                        log.warning(f"Anikoto megaplay extract error: {e}")

            except Exception as e:
                log.warning(f"Anikoto server resolve error: {e}")
                continue

        if not all_server_urls:
            log.error(f"Anikoto: no servers resolved for slug={slug} ep={episode_num}")
            return None

        return {
            "source": "anikoto",
            "master_url": best_master,
            "qualities": best_qualities,
            "servers": all_server_urls,
            "embed_url": best_embed,
            "total_episodes": total_episodes,
            "anime": anime_name,
        }

    except Exception as e:
        log.error(f"Anikoto stream error: {e}")
    return None


def _get_qualities(master_url):
    """Parse m3u8 master playlist for quality variants."""
    try:
        r = http_get(master_url, headers={"User-Agent": HEADERS["User-Agent"]})
        lines = r.text.strip().split("\n")
        qualities = []
        for i, line in enumerate(lines):
            if "RESOLUTION=" in line:
                res_match = re.search(r'RESOLUTION=(\d+x\d+)', line)
                if res_match and i + 1 < len(lines):
                    qualities.append({
                        "resolution": res_match.group(1),
                        "url": lines[i + 1].strip()
                    })
        return qualities
    except Exception:
        return []


# ──────────────────────────────────────────────
# Anikoto Homepage (cached 5 min)
# ──────────────────────────────────────────────

@cached(300)
def anikoto_homepage():
    """Scrape anikoto homepage for all sections. Cached 5 minutes."""
    empty = {"trending": [], "recent": [], "upcoming": [], "new_release": [],
             "new_added": [], "completed": [], "top_anime": []}
    try:
        resp = http_get(f"{ANIKOTO_DOMAIN}/home")
        if resp.status_code != 200:
            return empty
        soup = BeautifulSoup(resp.text, "html.parser")

        # Trending (hero slider)
        trending = []
        for slide in soup.select("#hotest .swiper-slide.item"):
            title_el = slide.select_one(".info h2.title.d-title")
            href_el = slide.select_one(".info .actions a.btn")
            bg_el = slide.select_one(".image div")
            synopsis_el = slide.select_one(".info .synopsis")
            rating_el = slide.select_one(".info .meta .rating")
            if not title_el or not href_el:
                continue
            trending.append({
                "title": title_el.get_text(strip=True),
                "slug": _extract_slug(href_el.get("href", "")),
                "cover": _parse_bg_image(bg_el.get("style", "")) if bg_el else "",
                "description": synopsis_el.get_text(strip=True) if synopsis_el else "",
                "rating": rating_el.get_text(strip=True) if rating_el else "",
                "source": "anikoto",
            })

        def _parse_ani_items(container):
            items = []
            for item in container.select(".item"):
                name_el = item.select_one(".info a.name.d-title")
                img_el = item.select_one(".ani.poster a img")
                if not name_el:
                    continue
                href = name_el.get("href", "")
                ep_match = re.search(r'/ep-(\d+)', href)
                sub_el = item.select_one(".ep-status.sub span")
                dub_el = item.select_one(".ep-status.dub span")
                total_el = item.select_one(".ep-status.total span")
                type_el = item.select_one(".meta .right")
                items.append({
                    "title": name_el.get_text(strip=True),
                    "slug": _extract_slug(href),
                    "cover": img_el.get("src", "") if img_el else "",
                    "episode": int(ep_match.group(1)) if ep_match else 0,
                    "sub": int(sub_el.get_text(strip=True)) if sub_el else 0,
                    "dub": int(dub_el.get_text(strip=True)) if dub_el else 0,
                    "total_episodes": int(total_el.get_text(strip=True)) if total_el else 0,
                    "type": type_el.get_text(strip=True) if type_el else "",
                    "source": "anikoto",
                })
            return items

        def _parse_top_table(section):
            items = []
            for a_tag in section.select(".scaff.items a.item"):
                img_el = a_tag.select_one(".poster span img")
                name_el = a_tag.select_one(".info .name.d-title")
                if not name_el:
                    continue
                sub_el = a_tag.select_one(".ep-status.sub span")
                dub_el = a_tag.select_one(".ep-status.dub span")
                items.append({
                    "title": name_el.get_text(strip=True),
                    "slug": _extract_slug(a_tag.get("href", "")),
                    "cover": img_el.get("src", "") if img_el else "",
                    "sub": int(sub_el.get_text(strip=True)) if sub_el else 0,
                    "dub": int(dub_el.get_text(strip=True)) if dub_el else 0,
                    "source": "anikoto",
                })
            return items

        recent_section = soup.select_one("#recent-update")
        recent = _parse_ani_items(recent_section.select_one(".ani.items")) if recent_section else []

        upcoming_section = soup.select_one("#upcoming-anime")
        upcoming = _parse_ani_items(upcoming_section.select_one(".ani.items")) if upcoming_section else []

        new_release_el = soup.select('section.top-table[data-name="new-release"]')
        new_release = _parse_top_table(new_release_el[0]) if new_release_el else []

        new_added_el = soup.select('section.top-table[data-name="new-added"]')
        new_added = _parse_top_table(new_added_el[0]) if new_added_el else []

        completed_el = soup.select('section.top-table[data-name="completed"]')
        completed = _parse_top_table(completed_el[0]) if completed_el else []

        top_anime = []
        top_section = soup.select_one("#top-anime")
        if top_section:
            for a_tag in top_section.select('.tab-content[data-name="day"] .scaff.side.items a.item'):
                img_el = a_tag.select_one(".poster span img")
                name_el = a_tag.select_one(".info .name.d-title")
                if not name_el:
                    continue
                rank_class = [c for c in a_tag.get("class", []) if c.startswith("rank")]
                rank = int(re.search(r'\d+', rank_class[0]).group()) if rank_class else 0
                sub_el = a_tag.select_one(".ep-status.sub span")
                dub_el = a_tag.select_one(".ep-status.dub span")
                top_anime.append({
                    "title": name_el.get_text(strip=True),
                    "slug": _extract_slug(a_tag.get("href", "")),
                    "cover": img_el.get("src", "") if img_el else "",
                    "rank": rank,
                    "sub": int(sub_el.get_text(strip=True)) if sub_el else 0,
                    "dub": int(dub_el.get_text(strip=True)) if dub_el else 0,
                    "source": "anikoto",
                })

        return {
            "trending": trending,
            "recent": recent,
            "upcoming": upcoming,
            "new_release": new_release,
            "new_added": new_added,
            "completed": completed,
            "top_anime": top_anime,
        }

    except Exception as e:
        log.error(f"Anikoto homepage error: {e}")
        return empty


@cached(300)
def anikoto_scrape_list(page_url, page=1, extra_params=None):
    """Generic scraper for any anikoto list page (genre, type, filter, latest-updated).
    Returns {results: [...], total_pages: N, current_page: N}."""
    empty = {"results": [], "total_pages": 1, "current_page": 1}
    try:
        url = f"{ANIKOTO_DOMAIN}{page_url}"
        params = {}
        if page > 1:
            params["page"] = page
        if extra_params:
            params.update(extra_params)
        resp = http_get(url, params=params if params else None)
        if resp.status_code != 200:
            log.error(f"Anikoto list scrape failed {resp.status_code} for {page_url}?page={page}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        container = soup.select_one("#list-items")
        if not container:
            return empty

        results = []
        for item in container.select(".item"):
            inner = item.select_one(".inner")
            if not inner:
                continue

            name_el = inner.select_one(".info a.name.d-title")
            img_el = inner.select_one(".ani.poster a img")
            if not name_el:
                continue

            href = name_el.get("href", "")
            slug = _extract_slug(href)
            title = name_el.get_text(strip=True)
            jp_title = name_el.get("data-jp", "")

            sub_el = inner.select_one(".ep-status.sub span")
            dub_el = inner.select_one(".ep-status.dub span")
            total_el = inner.select_one(".ep-status.total span")
            type_el = inner.select_one(".meta .right")

            genre_els = inner.select(".info .genre a")
            genres = [g.get_text(strip=True) for g in genre_els]

            rating_el = inner.select_one(".info .m-item.rated span")

            results.append({
                "title": title,
                "title_jp": jp_title,
                "slug": slug,
                "cover": img_el.get("src", "") if img_el else "",
                "sub": int(sub_el.get_text(strip=True)) if sub_el and sub_el.get_text(strip=True).isdigit() else 0,
                "dub": int(dub_el.get_text(strip=True)) if dub_el and dub_el.get_text(strip=True).isdigit() else 0,
                "total_episodes": int(total_el.get_text(strip=True)) if total_el and total_el.get_text(strip=True).isdigit() else 0,
                "type": type_el.get_text(strip=True) if type_el else "",
                "genres": genres,
                "rating": rating_el.get_text(strip=True) if rating_el else "",
                "source": "anikoto",
            })

        total_pages = 1
        page_links = soup.select(".pre-pagination .pagination .page-item a.page-link")
        for pl in page_links:
            href_val = pl.get("href", "")
            pm = re.search(r'page=(\d+)', href_val)
            if pm:
                pnum = int(pm.group(1))
                if pnum > total_pages:
                    total_pages = pnum

        return {"results": results, "total_pages": total_pages, "current_page": page}

    except Exception as e:
        log.error(f"Anikoto list scrape error for {page_url}: {e}")
        return empty


# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.endswith(('.js', '.css')) or path == '/':
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(NoCacheMiddleware)

app.include_router(nsfw_router)


# ──────────────────────────────────────────────
# URL Validation (security)
# ──────────────────────────────────────────────

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254",
                  "[::1]", "metadata.google.internal"}


def _is_safe_url(url):
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host in _BLOCKED_HOSTS:
            return False
        if host.startswith("10.") or host.startswith("192.168."):
            return False
        if host.startswith("172.") and 16 <= int(host.split(".")[1] or 0) <= 31:
            return False
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


# ──────────────────────────────────────────────
# Core API Routes
# ──────────────────────────────────────────────

@app.post("/stream")
async def stream_anime(req: StreamRequest):
    name = req.title
    result = None

    # Try slug directly
    if req.slug:
        log.info(f"[stream] Trying anikoto slug={req.slug} ep={req.episode}")
        result = anikoto_get_stream(req.slug, req.episode)
        if result:
            name = result.get("anime") or req.title

    # Fallback: search by title
    if not result and req.title:
        try:
            clean_title = re.sub(r'[,:\-!]', ' ', req.title).strip()
            clean_title = re.sub(r'\s+', ' ', clean_title)
            slug, sname = anikoto_search(clean_title)
            if slug:
                name = sname or req.title
                log.info(f"[stream] Trying anikoto search: {slug}")
                result = anikoto_get_stream(slug, req.episode)
        except Exception as e:
            log.error(f"[stream] Anikoto search error: {e}")

    if not result:
        log.error(f"[stream] FAILED title={req.title} slug={req.slug} ep={req.episode}")
        raise HTTPException(status_code=404, detail="Anime not found")

    # Enrich with AniList metadata (relations, description, etc.)
    anilist_meta = None
    relations = []
    try:
        search_name = re.sub(r'\s*\(\d{4}\)\s*$', '', name)
        al = anilist_search(search_name)
        if al and al.get("id"):
            full = anilist_detail(al["id"])
            if full:
                anilist_meta = full
                relations = full.get("relations", [])
    except Exception as e:
        log.warning(f"[stream] Anilist enrichment error: {e}")

    return {
        "status": "success",
        "anime": name,
        "episode": req.episode,
        "master_url": result.get("master_url"),
        "qualities": result.get("qualities", []),
        "embed_url": result.get("embed_url"),
        "servers": result.get("servers", []),
        "source": result.get("source", "anikoto"),
        "meta": {
            "episodes": result.get("total_episodes"),
            "anilist": anilist_meta,
            "relations": relations,
        },
    }


@app.get("/search")
async def search_anime(q: str = "", page: int = 1):
    if not q or len(q.strip()) < 2:
        return {"results": [], "total": 0, "has_next": False}
    query = q.strip()
    results = []
    try:
        resp = http_get(f"{ANIKOTO_DOMAIN}/search", params={"keyword": query, "page": page})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("#list-items .item"):
                name_el = item.select_one(".info .b1 .name.d-title")
                poster = item.select_one(".ani.poster")
                poster_link = poster.select_one("a") if poster else None
                img_el = item.select_one(".ani.poster img")
                if not name_el:
                    continue
                href = poster_link.get("href", "") if poster_link else ""
                title = name_el.get_text(strip=True)
                title_jp = name_el.get("data-jp", "")
                cover = img_el.get("src", "") if img_el else ""
                genres = [a.get_text(strip=True) for a in item.select(".info .b1 .genre a")]
                rating_el = item.select_one(".info .meta .m-item.rated span")
                rating = rating_el.get_text(strip=True) if rating_el else ""
                type_spans = item.select(".info .meta .m-item span")
                fmt = ""
                ep_count = ""
                for t_el in type_spans:
                    txt = t_el.get_text(strip=True)
                    if txt in ("TV", "Movie", "OVA", "ONA", "Special", "TV Short", "Music"):
                        fmt = txt
                    elif txt.isdigit():
                        ep_count = txt
                results.append({
                    "title": title,
                    "title_romaji": title_jp,
                    "slug": _extract_slug(href),
                    "cover": cover,
                    "score": float(rating) if rating and rating != "?" else None,
                    "format": fmt.upper().replace(" ", "_") if fmt else "",
                    "episodes": int(ep_count) if ep_count else None,
                    "genres": genres,
                    "source": "anikoto",
                })
            # Pagination
            page_links = soup.select(".pre-pagination .page-link")
            total_pages = 1
            for pl in page_links:
                pm = re.search(r'page=(\d+)', pl.get("href", ""))
                if pm:
                    total_pages = max(total_pages, int(pm.group(1)))
    except Exception as e:
        log.error(f"Search error: {e}")
    return {"results": results, "total": len(results), "has_next": page < total_pages}


@app.get("/anime/{anime_id}")
async def get_anime_detail(anime_id: int):
    meta = anilist_detail(anime_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Anime not found")
    return {"status": "success", "anime": meta}


@app.get("/api/anilist/search")
async def anilist_search_api(q: str = ""):
    if not q or len(q.strip()) < 2:
        return {"results": []}
    try:
        data = _anilist_gql(ANILIST_SEARCH_LIST_QUERY, {"search": q.strip(), "page": 1, "perPage": 5})
        media_list = data.get("Page", {}).get("media", [])
        results = []
        for m in media_list:
            results.append({
                "id": m["id"],
                "title": m["title"].get("english") or m["title"].get("romaji") or "",
                "cover": (m.get("coverImage") or {}).get("medium"),
                "format": m.get("format"),
                "episodes": m.get("episodes"),
                "status": m.get("status"),
                "score": m.get("averageScore"),
            })
        return {"results": results}
    except Exception as e:
        log.error(f"Anilist search API error: {e}")
        return {"results": []}


@app.get("/api/browse/genres")
async def browse_genres():
    genres = [
        ("action", "Action"), ("adventure", "Adventure"), ("boys-love", "Boys Love"),
        ("cars", "Cars"), ("comedy", "Comedy"), ("dementia", "Dementia"),
        ("demons", "Demons"), ("drama", "Drama"), ("ecchi", "Ecchi"),
        ("erotica", "Erotica"), ("fantasy", "Fantasy"), ("game", "Game"),
        ("girls-love", "Girls Love"), ("gourmet", "Gourmet"), ("harem", "Harem"),
        ("historical", "Historical"), ("horror", "Horror"), ("isekai", "Isekai"),
        ("josei", "Josei"), ("kids", "Kids"), ("magic", "Magic"),
        ("mahou-shoujo", "Mahou Shoujo"), ("martial-arts", "Martial Arts"),
        ("mecha", "Mecha"), ("military", "Military"), ("music", "Music"),
        ("mystery", "Mystery"), ("parody", "Parody"), ("police", "Police"),
        ("psychological", "Psychological"), ("romance", "Romance"),
        ("samurai", "Samurai"), ("school", "School"), ("sci-fi", "Sci-Fi"),
        ("seinen", "Seinen"), ("shoujo", "Shoujo"), ("shoujo-ai", "Shoujo Ai"),
        ("shounen", "Shounen"), ("shounen-ai", "Shounen Ai"),
        ("slice-of-life", "Slice of Life"), ("space", "Space"), ("sports", "Sports"),
        ("super-power", "Super Power"), ("supernatural", "Supernatural"),
        ("suspense", "Suspense"), ("thriller", "Thriller"), ("unknown", "Unknown"),
        ("vampire", "Vampire"),
    ]
    return {"genres": [{"slug": s, "name": n} for s, n in genres]}


@app.get("/api/browse/types")
async def browse_types():
    types = [
        ("tv", "TV"), ("movie", "Movie"), ("ova", "OVA"),
        ("ona", "ONA"), ("special", "Special"),
        ("tv-short", "TV Short"), ("tv-special", "TV Special"),
    ]
    return {"types": [{"slug": s, "name": n} for s, n in types]}


@app.get("/api/browse/latest")
async def browse_latest(page: int = 1):
    data = anikoto_scrape_list("/latest-updated", page)
    return data


@app.get("/api/browse/genre/{slug}")
async def browse_genre(slug: str, page: int = 1):
    data = anikoto_scrape_list(f"/genre/{slug}", page)
    return data


@app.get("/api/browse/type/{slug}")
async def browse_type(slug: str, page: int = 1):
    data = anikoto_scrape_list(f"/type/{slug}", page)
    return data


@app.get("/api/browse/filter")
async def browse_filter(
    page: int = 1,
    genre: str = "",
    term_type: str = "",
):
    extra = {}
    if genre:
        extra["genre[]"] = genre
    if term_type:
        extra["term_type[]"] = term_type
    data = anikoto_scrape_list("/filter", page, extra if extra else None)
    return data


@app.get("/api/browse")
async def browse_anime(section: str = ""):
    data = anikoto_homepage()
    section_order = ["trending", "recent", "upcoming", "new_release", "new_added", "completed"]
    sections = {k: data.get(k, []) for k in section_order}

    seen = set()
    all_items = []
    for key in section_order:
        for item in data.get(key, []):
            slug = item.get("slug", "")
            if slug and slug not in seen:
                seen.add(slug)
                all_items.append(item)

    if section and section in sections:
        results = sections[section]
    else:
        results = all_items

    return {"results": results, "total": len(results), "sections": section_order}


TRENDING_QUERY = """{ Page(page:1, perPage:15) { media(sort:TRENDING_DESC, type:ANIME) { id title { romaji } coverImage { large } format averageScore episodes status } } }"""


@app.get("/api/trending")
async def get_trending():
    try:
        data = _anilist_gql(TRENDING_QUERY, {})
        media_list = data.get("Page", {}).get("media", []) if data else []
        results = []
        for m in media_list:
            title_data = m.get("title") or {}
            results.append({
                "id": m.get("id"),
                "title": title_data.get("romaji") or "",
                "cover": (m.get("coverImage") or {}).get("large", ""),
                "score": m.get("averageScore"),
                "format": (m.get("format") or "").replace("_", " "),
                "episodes": m.get("episodes"),
                "status": m.get("status"),
            })
        return {"results": results}
    except Exception as e:
        log.error(f"Trending error: {e}")
        return {"results": []}


SCHEDULE_QUERY = """{ Page(page:1, perPage:60) { media(status:RELEASING, type:ANIME, sort:POPULARITY_DESC) { id title { romaji native } coverImage { large } bannerImage format genres averageScore nextAiringEpisode { episode airingAt timeUntilAiring } } } }"""


@cached(1800)
def _fetch_schedule_data():
    data = _anilist_gql(SCHEDULE_QUERY, {})
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    schedule = {d: [] for d in days}
    media_list = data.get("Page", {}).get("media", []) if data else []
    for m in media_list:
        na = m.get("nextAiringEpisode")
        if not na or not na.get("airingAt"):
            continue
        ts = na["airingAt"]
        import datetime
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        day_name = days[dt.weekday()]
        title_data = m.get("title", {})
        schedule[day_name].append({
            "id": m.get("id"),
            "title": title_data.get("romaji") or title_data.get("native") or "Unknown",
            "cover": (m.get("coverImage") or {}).get("large", ""),
            "banner": m.get("bannerImage") or "",
            "format": (m.get("format") or "").replace("_", " "),
            "genres": m.get("genres") or [],
            "score": m.get("averageScore"),
            "episode": na.get("episode"),
            "airing_at": ts,
            "time_until": na.get("timeUntilAiring", 0),
        })
    for d in days:
        schedule[d].sort(key=lambda x: x["airing_at"])
    return schedule


@app.get("/api/schedule")
async def get_schedule():
    schedule = _fetch_schedule_data()
    return {"schedule": schedule}


RECOMMENDATIONS_QUERY = """{ Media(id:%d, type:ANIME) { recommendations(page:1, perPage:12, sort:RATING_DESC) { edges { node { id mediaRecommendation { id title { romaji } coverImage { large } averageScore format genres } rating } } } } }"""


@app.get("/api/anilist/recommendations/{anime_id}")
async def get_anilist_recommendations(anime_id: int):
    try:
        data = _anilist_gql(RECOMMENDATIONS_QUERY % anime_id, {})
        edges = (data.get("Media") or {}).get("recommendations", {}).get("edges", [])
        results = []
        seen = set()
        for e in edges:
            m = e.get("node", {}).get("mediaRecommendation")
            if not m or not m.get("id") or m["id"] in seen:
                continue
            seen.add(m["id"])
            title_data = m.get("title") or {}
            results.append({
                "id": m["id"],
                "title": title_data.get("romaji") or "",
                "cover": (m.get("coverImage") or {}).get("large", ""),
                "score": m.get("averageScore"),
                "format": (m.get("format") or "").replace("_", " "),
                "genres": m.get("genres") or [],
            })
        return {"results": results}
    except Exception as e:
        log.error(f"Recommendations error: {e}")
        return {"results": []}


GENRE_SLUG_MAP = {
    "Action": "action", "Adventure": "adventure", "Comedy": "comedy",
    "Drama": "drama", "Fantasy": "fantasy", "Horror": "horror",
    "Mystery": "mystery", "Romance": "romance", "Sci-Fi": "sci-fi",
    "Slice of Life": "slice-of-life", "Sports": "sports",
    "Supernatural": "supernatural", "Thriller": "thriller",
    "Mecha": "mecha", "Psychological": "psychological",
    "Shounen": "shounen", "Seinen": "seinen",
    "Isekai": "isekai", "Music": "music",
}


@app.get("/api/similar")
async def get_similar(genre: str = "", exclude: str = ""):
    slug = GENRE_SLUG_MAP.get(genre, genre.lower().replace(" ", "-"))
    if not slug:
        return {"results": []}
    data = anikoto_scrape_list(f"/genre/{slug}", 1)
    results = data.get("results", [])
    if exclude:
        results = [r for r in results if r.get("slug") != exclude]
    return {"results": results[:12]}


# ──────────────────────────────────────────────
# Anikoto Homepage Routes (all share cached data)
# ──────────────────────────────────────────────

@app.get("/api/anikoto/homepage")
async def get_anikoto_homepage():
    data = anikoto_homepage()
    return {"status": "success", **data}


@app.get("/api/anikoto/trending")
async def get_anikoto_trending():
    data = anikoto_homepage()
    return {"results": data.get("trending", [])[:20]}


@app.get("/api/anikoto/recent")
async def get_anikoto_recent():
    data = anikoto_homepage()
    return {"results": data.get("recent", [])[:24]}


@app.get("/api/anikoto/upcoming")
async def get_anikoto_upcoming():
    data = anikoto_homepage()
    return {"results": data.get("upcoming", [])[:12]}


@app.get("/api/anikoto/new-release")
async def get_anikoto_new_release():
    data = anikoto_homepage()
    return {"results": data.get("new_release", [])[:12]}


@app.get("/api/anikoto/new-added")
async def get_anikoto_new_added():
    data = anikoto_homepage()
    return {"results": data.get("new_added", [])[:12]}


@app.get("/api/anikoto/completed")
async def get_anikoto_completed():
    data = anikoto_homepage()
    return {"results": data.get("completed", [])[:12]}


@app.get("/api/anikoto/top")
async def get_anikoto_top():
    data = anikoto_homepage()
    return {"results": data.get("top_anime", [])[:9]}


# ──────────────────────────────────────────────
# Proxy Routes
# ──────────────────────────────────────────────

@app.get("/resolve-embed")
async def resolve_embed(url: str):
    if not _is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        resp = http_get(url, headers={
            **HEADERS,
            "Referer": "https://gogoanimes.cv/",
        })
        text = resp.text
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', text, re.IGNORECASE)
        if iframes:
            iframe_src = iframes[0]
            if not iframe_src.startswith("http"):
                parsed = urlparse(url)
                iframe_src = f"{parsed.scheme}://{parsed.netloc}{iframe_src}"
            return {"url": iframe_src}
        m3u8 = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', text)
        if m3u8:
            return {"url": m3u8[0], "type": "hls"}
        return {"url": url}
    except Exception as e:
        return {"url": url, "error": str(e)}


@app.get("/proxy")
async def proxy_embed(url: str):
    if not _is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        resp = http_get(url, headers={
            **HEADERS,
            "Referer": "https://anitaku.com.ro/",
        })
        content = resp.text

        def fix_rel(m):
            prefix = m.group(1)
            path = m.group(2)
            if path.startswith(("http://", "https://", "//")):
                return m.group(0)
            return f'{prefix}{base}/{path.lstrip("/")}'

        content = re.sub(r'((?:src|href|action)=["\'])((?!https?://|//)[^"\']+)', fix_rel, content)

        if "4animo" in parsed.netloc:
            content = re.sub(r'fetch\(["\']((?!https?://|//)[^"\']+)', lambda m: f'fetch("{base}/{m.group(1).lstrip("/")}"', content)
            content = re.sub(r'url:\s*["\']((?!https?://|//)[^"\']+)', lambda m: f'url: "{base}/{m.group(1).lstrip("/")}"', content)
            content = re.sub(r'(["\'])(/stream/[^"\']*)', lambda m: f'{m.group(1)}{base}{m.group(2)}', content)
            content = re.sub(r'(["\'])(/p/[^"\']*)', lambda m: f'{m.group(1)}{base}{m.group(2)}', content)
            content = re.sub(r'(["\'])(/jwplayer/[^"\']*)', lambda m: f'{m.group(1)}{base}{m.group(2)}', content)

        return Response(content=content, media_type="text/html")
    except Exception as e:
        raise HTTPException(status_code=502, detail="Proxy error")


@app.get("/stream-proxy")
async def stream_proxy(url: str):
    if not _is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        resp = http_get(url, headers={
            **HEADERS,
            "Referer": "https://watchhentai.net/",
        }, timeout=30, stream=True)
        resp_headers = {
            "Content-Type": resp.headers.get("Content-Type", "video/mp4"),
            "Access-Control-Allow-Origin": "*",
        }
        if "Content-Length" in resp.headers:
            resp_headers["Content-Length"] = resp.headers["Content-Length"]
        if "Content-Range" in resp.headers:
            resp_headers["Content-Range"] = resp.headers["Content-Range"]

        def stream():
            try:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        yield chunk
            except Exception:
                pass
            finally:
                resp.close()

        return StreamingResponse(stream(), headers=resp_headers, media_type=resp_headers["Content-Type"])
    except Exception as e:
        raise HTTPException(status_code=502, detail="Stream proxy error")


# ──────────────────────────────────────────────
# Manga — MangaDex API
# ──────────────────────────────────────────────

MANGADEX_BASE = "https://api.mangadex.org"
MANGADEX_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_mangadex_cache: dict = {}
_mangadex_cache_ttl: dict = {}

def _mangadex_get(path: str, params=None, cache_ttl: int = 120) -> dict:
    if params is None:
        params_list = []
    elif isinstance(params, dict):
        params_list = list(params.items())
    else:
        params_list = list(params)
    key = path + "?" + str(sorted(params_list))
    now = time.time()
    if key in _mangadex_cache and now - _mangadex_cache_ttl.get(key, 0) < cache_ttl:
        return _mangadex_cache[key]
    try:
        r = requests.get(MANGADEX_BASE + path, params=params, headers=MANGADEX_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        _mangadex_cache[key] = data
        _mangadex_cache_ttl[key] = now
        return data
    except Exception as e:
        log.warning(f"MangaDex error: {e}")
        return {}


@app.get("/api/manga/search")
def manga_search(q: str = Query(""), page: int = Query(1), orig_lang: str = Query(None)):
    params = {"limit": 20, "offset": (page - 1) * 20, "order[followedCount]": "desc", "availableTranslatedLanguage[]": "en", "includes[]": "cover_art"}
    if q:
        params["title"] = q
    if orig_lang in ("ja", "ko", "zh"):
        params["originalLanguage[]"] = orig_lang
    data = _mangadex_get("/manga", params, cache_ttl=300)
    results = []
    for m in data.get("data", []):
        attrs = m["attributes"]
        title = attrs["title"].get("en") or (list(attrs["title"].values())[0] if attrs["title"] else "Unknown")
        orig = attrs.get("originalLanguage", "")
        mtype = {"ja": "Manga", "ko": "Manhwa", "zh": "Manhua"}.get(orig, "Manga")
        status_map = {1: "Ongoing", 2: "Completed", 3: "Cancelled", 4: "Hiatus"}
        status = status_map.get(attrs.get("status", 0), "Unknown")
        cover_url = ""
        for rel in m.get("relationships", []):
            if rel["type"] == "cover_art" and rel.get("attributes"):
                fn = rel["attributes"].get("fileName", "")
                raw_url = f"https://uploads.mangadex.org/covers/{m['id']}/{fn}"
                cover_url = f"/api/manga/cover?url={quote(raw_url, safe='')}"
        results.append({
            "id": m["id"], "title": title, "cover": cover_url,
            "type": mtype, "status": status,
            "tags": [t["attributes"]["name"].get("en", "") for t in attrs.get("tags", [])[:5]],
            "year": attrs.get("year"), "rating": attrs.get("followedCount", 0),
        })
    total = data.get("total", 0)
    total_pages = (total + 19) // 20
    return {"results": results, "total": total, "total_pages": total_pages, "page": page}


@app.get("/api/manga/proxy")
def manga_proxy(chapter_id: str = Query(..., alias="chapterId"), page: int = Query(0)):
    data = _mangadex_get(f"/at-home/server/{chapter_id}", cache_ttl=600)
    if "chapter" not in data:
        raise HTTPException(status_code=404, detail="Chapter not found")
    ch = data["chapter"]
    pages = ch.get("data", [])
    if page >= len(pages):
        raise HTTPException(status_code=404, detail="Page out of range")
    url = f'{data["baseUrl"]}/data/{ch["hash"]}/{pages[page]}'
    try:
        r = requests.get(url, headers={**MANGADEX_HEADERS, "Referer": "https://mangadex.org/"}, timeout=TIMEOUT, stream=True)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "image/jpeg")
        return StreamingResponse(r.iter_content(1024), media_type=ct, headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        log.warning(f"Manga proxy error: {e}")
        raise HTTPException(status_code=502, detail="Image proxy error")


@app.get("/api/manga/cover")
def manga_cover_proxy(url: str = Query(...)):
    """Proxy MangaDex cover images with correct Referer to bypass hotlink protection."""
    if not url.startswith("https://uploads.mangadex.org/covers/"):
        raise HTTPException(status_code=400, detail="Invalid cover URL")
    try:
        r = requests.get(url, headers={**MANGADEX_HEADERS, "Referer": "https://mangadex.org/"}, timeout=TIMEOUT, stream=True)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "image/jpeg")
        return StreamingResponse(r.iter_content(1024), media_type=ct, headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        log.warning(f"Cover proxy error: {e}")
        raise HTTPException(status_code=502, detail="Cover proxy error")


@app.get("/api/manga/chapter/{chapter_id}")
def manga_chapter_images(chapter_id: str):
    data = _mangadex_get(f"/at-home/server/{chapter_id}", cache_ttl=600)
    if "chapter" not in data:
        raise HTTPException(status_code=404, detail="Chapter not found")
    ch = data["chapter"]
    return {
        "baseUrl": data.get("baseUrl", ""),
        "hash": ch.get("hash", ""),
        "pages": ch.get("data", []),
        "pagesSaver": ch.get("dataSaver", []),
    }


@app.get("/api/manga/{manga_id}")
def manga_detail(manga_id: str):
    data = _mangadex_get(f"/manga/{manga_id}", [("includes[]", "cover_art"), ("includes[]", "author")], cache_ttl=300)
    m = data.get("data")
    if not m:
        raise HTTPException(status_code=404, detail="Manga not found")
    attrs = m["attributes"]
    title = attrs["title"].get("en") or (list(attrs["title"].values())[0] if attrs["title"] else "Unknown")
    alt_titles = []
    for at in attrs.get("altTitles", []):
        for v in at.values():
            if v and v != title:
                alt_titles.append(v)
    orig = attrs.get("originalLanguage", "")
    mtype = {"ja": "Manga", "ko": "Manhwa", "zh": "Manhua"}.get(orig, "Manga")
    status_map = {1: "Ongoing", 2: "Completed", 3: "Cancelled", 4: "Hiatus"}
    status = status_map.get(attrs.get("status", 0), "Unknown")
    cover_url = ""
    for rel in m.get("relationships", []):
        if rel["type"] == "cover_art" and rel.get("attributes"):
            fn = rel["attributes"].get("fileName", "")
            raw_url = f"https://uploads.mangadex.org/covers/{manga_id}/{fn}"
            cover_url = f"/api/manga/cover?url={quote(raw_url, safe='')}"
    authors = [r.get("attributes", {}).get("name", "") for r in m.get("relationships", []) if r["type"] == "author"]
    return {
        "id": manga_id, "title": title, "cover": cover_url,
        "type": mtype, "status": status,
        "synopsis": attrs.get("description", {}).get("en", ""),
        "genres": [t["attributes"]["name"].get("en", "") for t in attrs.get("tags", [])],
        "year": attrs.get("year"),
        "alt_titles": alt_titles[:5],
        "authors": authors,
    }


@app.get("/api/manga/{manga_id}/chapters")
def manga_chapters(manga_id: str, lang: str = Query("en"), page: int = Query(1)):
    params = {
        "translatedLanguage[]": lang,
        "limit": 100,
        "offset": (page - 1) * 100,
        "order[chapter]": "desc",
        "includes[]": "scanlation_group",
    }
    data = _mangadex_get(f"/manga/{manga_id}/feed", params, cache_ttl=300)
    chapters = []
    for c in data.get("data", []):
        a = c["attributes"]
        if a.get("isUnavailable"):
            continue
        external = a.get("externalUrl") or ""
        grp_name = ""
        grp_id = ""
        for r in c.get("relationships", []):
            if r["type"] == "scanlation_group":
                grp_name = r.get("attributes", {}).get("name", "")
                grp_id = r.get("id", "")
        chapters.append({
            "id": c["id"],
            "chapter": a.get("chapter"),
            "title": a.get("title") or "",
            "volume": a.get("volume"),
            "pages": a.get("pages", 0),
            "lang": a.get("translatedLanguage", ""),
            "publishAt": a.get("publishAt", ""),
            "group": grp_name,
            "group_id": grp_id,
            "external": external,
        })
    total = data.get("total", 0)
    return {"chapters": chapters, "total": total, "total_pages": (total + 99) // 100, "page": page}


@app.get("/api/manga/{manga_id}/recommended")
def manga_recommended(manga_id: str):
    detail = _mangadex_get(f"/manga/{manga_id}", [("includes[]", "tag")], cache_ttl=300)
    m = detail.get("data")
    if not m:
        return {"results": []}
    tag_ids = [t["id"] for t in m["attributes"].get("tags", [])[:3]]
    if not tag_ids:
        return {"results": []}
    params = [
        ("limit", 10),
        ("order[followedCount]", "desc"),
        ("availableTranslatedLanguage[]", "en"),
        ("includes[]", "cover_art"),
    ]
    for tid in tag_ids:
        params.append(("includedTags[]", tid))
    data = _mangadex_get("/manga", params, cache_ttl=600)
    results = []
    for rm in data.get("data", []):
        if rm["id"] == manga_id:
            continue
        attrs = rm["attributes"]
        title = attrs["title"].get("en") or (list(attrs["title"].values())[0] if attrs["title"] else "Unknown")
        orig = attrs.get("originalLanguage", "")
        mtype = {"ja": "Manga", "ko": "Manhwa", "zh": "Manhua"}.get(orig, "Manga")
        cover_url = ""
        for rel in rm.get("relationships", []):
            if rel["type"] == "cover_art" and rel.get("attributes"):
                fn = rel["attributes"].get("fileName", "")
                raw_url = f"https://uploads.mangadex.org/covers/{rm['id']}/{fn}"
                cover_url = f"/api/manga/cover?url={quote(raw_url, safe='')}"
        results.append({
            "id": rm["id"], "title": title, "cover": cover_url, "type": mtype,
        })
    return {"results": results[:8]}


# ──────────────────────────────────────────────
# Static Files & HTML Pages
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return FileResponse(os.path.join(DIR, "index.html"))


@app.get("/styles.css")
def serve_css():
    return FileResponse(os.path.join(DIR, "styles.css"), media_type="text/css")


@app.get("/data.js")
def serve_data_js():
    return FileResponse(os.path.join(DIR, "data.js"), media_type="application/javascript")


@app.get("/site.js")
def serve_site_js():
    return FileResponse(os.path.join(DIR, "site.js"), media_type="application/javascript")


# HTML page routes
for _page in [
    "browse", "search", "details", "watch", "genre", "studio", "season",
    "schedule", "top", "trending", "recent", "new-releases", "popular",
    "movies", "ovas", "onas", "tv-series", "mylist", "manga", "manga-detail", "reader",
]:
    _path = f"/{_page}.html"
    _file = os.path.join(DIR, f"{_page}.html")
    if os.path.exists(_file):
        app.get(_path, response_class=HTMLResponse)(lambda f=_file: FileResponse(f))

# Short route aliases (e.g. /browse -> browse.html)
for _page in ["browse", "search", "details", "watch", "genre", "studio", "season",
              "schedule", "top", "trending", "recent", "new-releases", "popular",
              "movies", "ovas", "onas", "tv-series", "mylist", "manga", "manga-detail", "reader"]:
    _file = os.path.join(DIR, f"{_page}.html")
    if os.path.exists(_file):
        app.get(f"/{_page}", response_class=HTMLResponse)(lambda f=_file: FileResponse(f))

if os.path.exists(os.path.join(DIR, "public")):
    app.mount("/public", StaticFiles(directory=os.path.join(DIR, "public")), name="public")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
