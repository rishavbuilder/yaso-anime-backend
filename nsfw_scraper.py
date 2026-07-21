# nsfw_scraper.py — NSFW Content Scraper
# Sources: hanime.tv (homepage, trending), ohentai.org (search, detail, stream)

import re, time, logging, base64
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("nsfw")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

HANIME_DOMAIN = "https://hanime.tv"
OHENTAI_DOMAIN = "https://ohentai.org"
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ──────────────────────────────────────────────
# HTTP Session
# ──────────────────────────────────────────────

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=2, pool_connections=10, pool_maxsize=20)
session.mount("https://", adapter)
session.mount("http://", adapter)


def http_get(url, **kwargs):
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", TIMEOUT)
    return session.get(url, **kwargs)


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


def _extract_slug(href):
    """Extract slug from URL like /videos/hentai/slug-name"""
    m = re.search(r'/videos/hentai/([a-z0-9][a-z0-9-]+)', href, re.IGNORECASE)
    return m.group(1) if m else href.strip('/').split('/')[-1]


def _parse_views(text):
    """Parse view count like '2.2M' -> 2200000"""
    text = text.strip().replace(',', '')
    if not text:
        return 0
    multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
    for suffix, mult in multipliers.items():
        if text.upper().endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(text)
    except ValueError:
        return 0


def _parse_views_str(text):
    """Keep views as string like '2.2M' for display"""
    return text.strip() if text else "0"


# ══════════════════════════════════════════════
# HANIME.TV SCRAPER
# ══════════════════════════════════════════════

def _hanime_parse_card(item_el):
    """Parse a single hanime card element into standard dict."""
    try:
        # Try to find link - could be <a> directly or nested
        link = item_el.select_one("a[href*='/videos/hentai/']")
        if not link:
            link = item_el.select_one("a")
        if not link:
            return None

        href = link.get("href", "")
        slug = _extract_slug(href)

        # Best title source: <a title="Watch X hentai stream..."> attribute
        title_attr = link.get("title", "")
        title = ""
        if title_attr:
            # Extract: "Watch Title Here hentai stream online HD 1080p, 720p" -> "Title Here"
            m = re.match(r'^Watch\s+(.+?)\s+hentai\s+stream', title_attr, re.I)
            if m:
                title = m.group(1).strip()

        # Fallback: slug to title
        if not title and slug:
            title = slug.replace('-', ' ').title()

        # Get cover image
        img_el = link.select_one("img")
        cover = ""
        if img_el:
            cover = img_el.get("src") or img_el.get("data-src") or ""
            if cover and not cover.startswith("http"):
                cover = "https:" + cover

        # Views: look in div text for view count pattern
        views = "0"
        for div in link.select("div"):
            text = div.get_text(strip=True)
            view_match = re.search(r'([\d.]+[KMB])', text)
            if view_match:
                views = view_match.group(1)
                break

        if not title:
            return None

        return {
            "title": title,
            "slug": slug,
            "cover": cover,
            "views": views,
            "episode": 1,
            "sub": 0,
            "dub": 1,
            "total_episodes": 1,
            "type": "OVA",
            "rating": "",
            "genres": [],
            "source": "hanime",
            "nsfw": True,
        }
    except Exception as e:
        log.error(f"Hanime card parse error: {e}")
        return None


@cached(300)
def hanime_homepage():
    """Scrape hanime.tv homepage. Returns standard section dict."""
    empty = {"trending": [], "recent": [], "upcoming": [], "new_release": [],
             "new_added": [], "completed": [], "top_anime": []}
    try:
        resp = http_get(f"{HANIME_DOMAIN}/")
        if resp.status_code != 200:
            log.error(f"Hanime homepage {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")

        # Recent Uploads section
        recent = []
        recent_heading = soup.find("h2", string=re.compile(r"Recent Uploads", re.I))
        if recent_heading:
            section = recent_heading.find_parent("section") or recent_heading.parent
            if section:
                for card in section.select(".card, .item, article, a[href*='/videos/hentai/']")[:24]:
                    parsed = _hanime_parse_card(card)
                    if parsed:
                        recent.append(parsed)

        # Fallback: parse all video links from homepage using title attribute
        if not recent:
            for a_tag in soup.select('a[href*="/videos/hentai/"]')[:24]:
                href = a_tag.get("href", "")
                slug = _extract_slug(href)
                # Use title attribute for clean title
                title_attr = a_tag.get("title", "")
                title = ""
                if title_attr:
                    m = re.match(r'^Watch\s+(.+?)\s+hentai\s+stream', title_attr, re.I)
                    if m:
                        title = m.group(1).strip()
                if not title:
                    title = slug.replace('-', ' ').title()

                img_el = a_tag.select_one("img")
                cover = ""
                if img_el:
                    cover = img_el.get("src") or img_el.get("data-src") or ""
                    if cover and not cover.startswith("http"):
                        cover = "https:" + cover

                views = "0"
                for div in a_tag.select("div"):
                    text = div.get_text(strip=True)
                    vm = re.search(r'([\d.]+[KMB])', text)
                    if vm:
                        views = vm.group(1)
                        break

                if title and slug:
                    recent.append({
                        "title": title,
                        "slug": slug,
                        "cover": cover,
                        "views": views,
                        "episode": 1, "sub": 0, "dub": 1,
                        "total_episodes": 1, "type": "OVA", "rating": "",
                        "genres": [], "source": "hanime", "nsfw": True,
                    })

        # New Releases section
        new_release = []
        new_heading = soup.find("h2", string=re.compile(r"New Releases", re.I))
        if new_heading:
            section = new_heading.find_parent("section") or new_heading.parent
            if section:
                for card in section.select(".card, .item, article")[:12]:
                    parsed = _hanime_parse_card(card)
                    if parsed:
                        new_release.append(parsed)

        # Trending section (from homepage cards)
        trending = []
        trending_heading = soup.find("h2", string=re.compile(r"Trending", re.I))
        if trending_heading:
            section = trending_heading.find_parent("section") or trending_heading.parent
            if section:
                for card in section.select(".card, .item, article")[:20]:
                    parsed = _hanime_parse_card(card)
                    if parsed:
                        trending.append(parsed)

        return {
            "trending": trending or recent[:20],
            "recent": recent,
            "upcoming": [],
            "new_release": new_release or recent[:12],
            "new_added": recent[:12],
            "completed": [],
            "top_anime": trending[:9] if trending else recent[:9],
        }

    except Exception as e:
        log.error(f"Hanime homepage error: {e}")
        return empty


@cached(300)
def hanime_trending(timespan="monthly"):
    """Scrape hanime.tv trending page."""
    empty = {"results": [], "total_pages": 1, "current_page": 1}
    try:
        resp = http_get(f"{HANIME_DOMAIN}/browse/trending", params={"timespan": timespan})
        if resp.status_code != 200:
            log.error(f"Hanime trending {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # Parse trending cards
        for a_tag in soup.select('a[href*="/videos/hentai/"]'):
            href = a_tag.get("href", "")
            slug = _extract_slug(href)
            title_el = a_tag.select_one("h5") or a_tag.select_one("h4")
            title = title_el.get_text(strip=True) if title_el else ""
            img_el = a_tag.select_one("img")
            cover = ""
            if img_el:
                cover = img_el.get("src") or img_el.get("data-src") or ""
                if cover and not cover.startswith("http"):
                    cover = "https:" + cover
            views_el = a_tag.select_one("span")
            views = _parse_views_str(views_el.get_text(strip=True)) if views_el else "0"

            if title and slug:
                results.append({
                    "title": title,
                    "slug": slug,
                    "cover": cover,
                    "views": views,
                    "episode": 1, "sub": 0, "dub": 1,
                    "total_episodes": 1, "type": "OVA", "rating": "",
                    "genres": [], "source": "hanime", "nsfw": True,
                })

        return {"results": results, "total_pages": 1, "current_page": 1}

    except Exception as e:
        log.error(f"Hanime trending error: {e}")
        return empty


@cached(300)
def hanime_search(query, page=1):
    """Search hanime.tv - fallback to ohentai since hanime search is JS-rendered."""
    return ohentai_search(query, page)


# ══════════════════════════════════════════════
# OHENTAI.ORG SCRAPER
# ══════════════════════════════════════════════

def _ohentai_parse_card(item_el):
    """Parse ohentai card."""
    try:
        link = item_el.select_one("a[href*='detail.php?vid=']")
        if not link:
            link = item_el.select_one("a")
        if not link:
            return None

        href = link.get("href", "")
        # Extract vid from detail.php?vid=XXXX
        vid_match = re.search(r'vid=([A-Za-z0-9+/=]+)', href)
        vid = vid_match.group(1) if vid_match else ""

        # Title: try img alt first (cleanest), then text
        title = ""
        img_el = link.select_one("img")
        if img_el:
            title = img_el.get("alt", "").strip()

        if not title:
            # Get text from h4/h5 inside the link
            for sel in ["h4", "h5", "h3"]:
                title_el = link.select_one(sel)
                if title_el:
                    title = title_el.get_text(strip=True)
                    break

        if not title:
            # Fallback: direct text children only
            for child in link.children:
                if isinstance(child, str) and child.strip() and len(child.strip()) > 2:
                    title = child.strip()
                    break

        cover = ""
        if img_el:
            cover = img_el.get("src") or img_el.get("data-src") or ""
            if cover and not cover.startswith("http"):
                cover = OHENTAI_DOMAIN + "/" + cover.lstrip("/")

        # Views: look for numbers pattern "1192152 | 96999"
        views = "0"
        full_text = item_el.get_text()
        views_match = re.search(r'([\d,]+)\s*\|', full_text)
        if views_match:
            views = views_match.group(1).replace(',', '')

        # Skip non-content items (like "Newest", "Raw", "SUBBED" labels alone)
        skip_words = {"newest", "raw", "subbed", "sponsored", "favorite"}
        if not title or title.lower() in skip_words or len(title) < 3:
            return None

        # Must have a valid vid
        if not vid:
            return None

        # Detect if subbed
        is_subbed = bool(re.search(r'subbed|sub\b', full_text, re.I))

        return {
            "title": title,
            "slug": vid,
            "cover": cover,
            "views": views,
            "episode": _extract_episode(title),
            "sub": 1 if is_subbed else 0,
            "dub": 0,
            "total_episodes": 0,
            "type": "OVA",
            "rating": "",
            "genres": [],
            "source": "ohentai",
            "nsfw": True,
            "vid": vid,
        }
    except Exception as e:
        log.error(f"OHentai card parse error: {e}")
        return None


def _extract_episode(title):
    """Extract episode number from title like 'Episode 3' -> 3"""
    m = re.search(r'episode\s*(\d+)', title, re.I)
    return int(m.group(1)) if m else 1


def _decode_vid(vid_str):
    """Decode base64 vid from ohentai."""
    try:
        # Add padding if needed
        padded = vid_str + '=' * (4 - len(vid_str) % 4) if len(vid_str) % 4 else vid_str
        decoded = base64.b64decode(padded).decode('utf-8')
        return decoded
    except Exception:
        return vid_str


@cached(300)
def ohentai_homepage(page=1):
    """Scrape ohentai.org homepage."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        url = OHENTAI_DOMAIN
        if page > 1:
            url = f"{OHENTAI_DOMAIN}/index.php?page={page}"

        resp = http_get(url)
        if resp.status_code != 200:
            log.error(f"OHentai homepage {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # ohentai uses divs with video cards
        for item in soup.select(".video-item, .item, .thumb-item, div[class*='video']"):
            parsed = _ohentai_parse_card(item)
            if parsed:
                results.append(parsed)

        # Fallback: parse any link to detail.php?vid=
        if not results:
            for a_tag in soup.select('a[href*="detail.php?vid="]'):
                href = a_tag.get("href", "")
                vid_match = re.search(r'vid=([A-Za-z0-9+/=]+)', href)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                title = a_tag.get_text(strip=True)
                img_el = a_tag.select_one("img")
                cover = ""
                if img_el:
                    cover = img_el.get("src") or ""
                    if cover and not cover.startswith("http"):
                        cover = OHENTAI_DOMAIN + "/" + cover.lstrip("/")

                if title and len(title) > 2:
                    results.append({
                        "title": title,
                        "slug": vid,
                        "cover": cover,
                        "views": "0",
                        "episode": _extract_episode(title),
                        "sub": 0, "dub": 0,
                        "total_episodes": 0, "type": "OVA", "rating": "",
                        "genres": [], "source": "ohentai", "nsfw": True,
                        "vid": vid,
                    })

        # Deduplicate by vid/slug
        seen = set()
        unique_results = []
        for r in results:
            key = r.get("vid") or r.get("slug")
            if key and key not in seen:
                seen.add(key)
                unique_results.append(r)

        return {"results": unique_results, "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"OHentai homepage error: {e}")
        return empty


@cached(300)
def ohentai_search(query, page=1):
    """Search ohentai.org."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(f"{OHENTAI_DOMAIN}/search.php", params={"keyword": query})
        if resp.status_code != 200:
            log.error(f"OHentai search {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for item in soup.select(".video-item, .item, .thumb-item, div[class*='video']"):
            parsed = _ohentai_parse_card(item)
            if parsed:
                results.append(parsed)

        # Fallback
        if not results:
            for a_tag in soup.select('a[href*="detail.php?vid="]'):
                href = a_tag.get("href", "")
                vid_match = re.search(r'vid=([A-Za-z0-9+/=]+)', href)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                title = a_tag.get_text(strip=True)
                img_el = a_tag.select_one("img")
                cover = ""
                if img_el:
                    cover = img_el.get("src") or ""
                    if cover and not cover.startswith("http"):
                        cover = OHENTAI_DOMAIN + "/" + cover.lstrip("/")

                if title and len(title) > 2:
                    results.append({
                        "title": title,
                        "slug": vid,
                        "cover": cover,
                        "views": "0",
                        "episode": _extract_episode(title),
                        "sub": 0, "dub": 0,
                        "total_episodes": 0, "type": "OVA", "rating": "",
                        "genres": [], "source": "ohentai", "nsfw": True,
                        "vid": vid,
                    })

        return {"results": results, "total": len(results), "has_next": False}

    except Exception as e:
        log.error(f"OHentai search error: {e}")
        return empty


@cached(300)
def ohentai_tag(tag, page=1):
    """Browse ohentai by tag."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(f"{OHENTAI_DOMAIN}/tagsearch.php", params={"tag": tag})
        if resp.status_code != 200:
            log.error(f"OHentai tag {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for item in soup.select(".video-item, .item, .thumb-item, div[class*='video']"):
            parsed = _ohentai_parse_card(item)
            if parsed:
                results.append(parsed)

        if not results:
            for a_tag in soup.select('a[href*="detail.php?vid="]'):
                href = a_tag.get("href", "")
                vid_match = re.search(r'vid=([A-Za-z0-9+/=]+)', href)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                title = a_tag.get_text(strip=True)
                img_el = a_tag.select_one("img")
                cover = ""
                if img_el:
                    cover = img_el.get("src") or ""
                    if cover and not cover.startswith("http"):
                        cover = OHENTAI_DOMAIN + "/" + cover.lstrip("/")

                if title and len(title) > 2:
                    results.append({
                        "title": title,
                        "slug": vid,
                        "cover": cover,
                        "views": "0",
                        "episode": _extract_episode(title),
                        "sub": 0, "dub": 0,
                        "total_episodes": 0, "type": "OVA", "rating": "",
                        "genres": [], "source": "ohentai", "nsfw": True,
                        "vid": vid,
                    })

        return {"results": results, "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"OHentai tag error: {e}")
        return empty


@cached(600)
def ohentai_detail(vid):
    """Get detail + stream URLs from ohentai detail page."""
    try:
        resp = http_get(f"{OHENTAI_DOMAIN}/detail.php", params={"vid": vid})
        if resp.status_code != 200:
            log.error(f"OHentai detail {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title_el = soup.select_one("h1") or soup.select_one("h2")
        title = title_el.get_text(strip=True) if title_el else ""

        # Cover
        cover_el = soup.select_one("img[src*='video_data']")
        cover = ""
        if cover_el:
            cover = cover_el.get("src") or ""
            if cover and not cover.startswith("http"):
                cover = OHENTAI_DOMAIN + "/" + cover.lstrip("/")

        # Description
        desc_el = soup.select_one(".description, .synopsis, p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Tags / Genres
        genres = []
        for tag_el in soup.select('a[href*="tagsearch.php?tag="]'):
            tag_text = tag_el.get_text(strip=True)
            if tag_text and tag_text not in genres:
                genres.append(tag_text)

        # Views
        views_text = soup.get_text()
        views_match = re.search(r'([\d,]+)\s*views', views_text, re.I)
        views = views_match.group(1).replace(',', '') if views_match else "0"

        # Stream URLs - look for external links
        stream_urls = []
        for a_tag in soup.select('a[href]'):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True).lower()
            # Look for known video hosts
            if any(host in href for host in ["fileone.tv", "dood.watch", "doodstream",
                                              "mp4upload", "streamtape", "fembed",
                                              "vidoza", "mixdrop", "streamsb"]):
                stream_urls.append({
                    "label": a_tag.get_text(strip=True),
                    "url": href,
                })

        # Also check for iframe sources
        for iframe in soup.select("iframe[src]"):
            src = iframe.get("src", "")
            if src and not src.startswith("//"):
                stream_urls.append({"label": "Embedded", "url": src})

        # Series info
        series_el = soup.select_one('a[href*="sery_video.php"]')
        series_name = ""
        series_id = ""
        if series_el:
            series_name = series_el.get_text(strip=True)
            sery_match = re.search(r'seryid=([A-Za-z0-9+/=]+)', series_el.get("href", ""))
            series_id = sery_match.group(1) if sery_match else ""

        # Series episodes
        series_episodes = []
        if series_id:
            try:
                sery_resp = http_get(f"{OHENTAI_DOMAIN}/sery_video.php", params={"seryid": series_id})
                if sery_resp.status_code == 200:
                    sery_soup = BeautifulSoup(sery_resp.text, "html.parser")
                    for ep_link in sery_soup.select('a[href*="detail.php?vid="]'):
                        ep_href = ep_link.get("href", "")
                        ep_vid_match = re.search(r'vid=([A-Za-z0-9+/=]+)', ep_href)
                        ep_title = ep_link.get_text(strip=True)
                        if ep_vid_match and ep_title:
                            series_episodes.append({
                                "title": ep_title,
                                "vid": ep_vid_match.group(1),
                            })
            except Exception as e:
                log.error(f"OHentai series fetch error: {e}")

        return {
            "title": title,
            "slug": vid,
            "cover": cover,
            "description": description,
            "views": views,
            "genres": genres,
            "stream_urls": stream_urls,
            "series_name": series_name,
            "series_episodes": series_episodes,
            "source": "ohentai",
            "nsfw": True,
        }

    except Exception as e:
        log.error(f"OHentai detail error: {e}")
        return None


# ══════════════════════════════════════════════
# COMBINED ENDPOINTS (for API routing)
# ══════════════════════════════════════════════

def nsfw_homepage():
    """Combined homepage from hanime + ohentai."""
    hanime_data = hanime_homepage()
    ohentai_data = ohentai_homepage()

    # Merge: use hanime for trending/recent, ohentai as supplement
    return {
        "trending": hanime_data.get("trending", []) or ohentai_data.get("results", [])[:20],
        "recent": hanime_data.get("recent", []) or ohentai_data.get("results", [])[:24],
        "upcoming": [],
        "new_release": hanime_data.get("new_release", []) or ohentai_data.get("results", [])[:12],
        "new_added": hanime_data.get("new_added", []) or ohentai_data.get("results", [])[:12],
        "completed": [],
        "top_anime": hanime_data.get("top_anime", []) or ohentai_data.get("results", [])[:9],
    }


def nsfw_search(query, page=1):
    """Search across hanime + ohentai."""
    results = []

    # ohentai search (hanime search is JS-rendered)
    ohentai_results = ohentai_search(query, page)
    results.extend(ohentai_results.get("results", []))

    return {
        "results": results,
        "total": len(results),
        "has_next": False,
    }


def nsfw_trending():
    """Get trending from hanime."""
    data = hanime_trending("monthly")
    return {"results": data.get("results", [])[:20]}


def nsfw_recent():
    """Get recent uploads."""
    data = hanime_homepage()
    return {"results": data.get("recent", [])[:24]}


def nsfw_new_release():
    """Get new releases."""
    data = hanime_homepage()
    return {"results": data.get("new_release", [])[:12]}


def nsfw_new_added():
    """Get newly added."""
    data = hanime_homepage()
    return {"results": data.get("new_added", [])[:12]}


def nsfw_completed():
    """Get completed series."""
    data = hanime_homepage()
    return {"results": data.get("completed", [])[:12]}


def nsfw_top():
    """Get top rated."""
    data = hanime_trending("monthly")
    return {"results": data.get("results", [])[:9]}


def nsfw_detail(slug):
    """Get detail - try ohentai vid first, then hanime slug."""
    # If slug looks like a base64 vid, use ohentai
    if re.match(r'^[A-Za-z0-9+/=]{4,}$', slug):
        return ohentai_detail(slug)
    # Otherwise try hanime
    return None


def nsfw_stream(slug):
    """Get stream URL for a video."""
    detail = nsfw_detail(slug)
    if detail and detail.get("stream_urls"):
        return detail["stream_urls"][0].get("url", "")
    return ""
