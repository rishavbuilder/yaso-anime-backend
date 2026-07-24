# nsfw_scraper.py — NSFW Content Scraper
# Sources: hanime.tv, ohentai.org, hentaistream.com, latesthentai.com, hentaiyes.com

import re, time, logging, base64
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("nsfw")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

HANIME_DOMAIN = "https://hanime.tv"
OHENTAI_DOMAIN = "https://ohentai.org"
HENTAISTREAM_DOMAIN = "https://tube.hentaistream.com"
LATESTHENTAI_DOMAIN = "https://latesthentai.com"
HENTAIYES_DOMAIN = "https://hentaiyes.com"
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
# HENTAISTREAM.COM SCRAPER
# ══════════════════════════════════════════════

def _hentaistream_parse_card(item_el):
    """Parse a hentaistream episode card."""
    try:
        link = item_el.select_one("a[href]")
        if not link:
            return None

        href = link.get("href", "")
        # Extract slug from full URL or relative
        slug_match = re.search(r'hentaistream\.com/([^/]+)', href)
        if slug_match:
            slug = slug_match.group(1)
        else:
            slug = href.strip("/").split("/")[-1]

        if not slug or slug in ("genres", "hentai-series-list-full-shows", "hentai-most-viewed-episodes-all"):
            return None

        # Title from img alt or link text
        title = ""
        img_el = link.select_one("img")
        if img_el:
            title = img_el.get("alt", "").strip() or img_el.get("title", "").strip()

        if not title:
            title = link.get_text(strip=True)

        if not title:
            title = slug.replace("-", " ").title()

        # Cover image
        cover = ""
        if img_el:
            cover = img_el.get("src") or img_el.get("data-src") or ""
            if cover and not cover.startswith("http"):
                cover = HENTAISTREAM_DOMAIN + cover

        # Views from text
        views = "0"
        view_el = item_el.select_one(".view, .views")
        if view_el:
            vm = re.search(r'([\d,]+)', view_el.get_text())
            if vm:
                views = vm.group(1).replace(",", "")

        if not views or views == "0":
            full_text = item_el.get_text()
            vm = re.search(r'([\d,]+)\s*views?', full_text, re.I)
            if vm:
                views = vm.group(1).replace(",", "")

        return {
            "title": title,
            "slug": slug,
            "cover": cover,
            "views": views,
            "episode": _extract_episode(title),
            "sub": 0, "dub": 0,
            "total_episodes": 0, "type": "OVA", "rating": "",
            "genres": [], "source": "hentaistream", "nsfw": True,
        }
    except Exception as e:
        log.error(f"HentaiStream card parse error: {e}")
        return None


@cached(300)
def hentaistream_homepage(page=1):
    """Scrape hentaistream.com homepage."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(HENTAISTREAM_DOMAIN)
        if resp.status_code != 200:
            log.error(f"HentaiStream homepage {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # Parse episode links from homepage
        for a_tag in soup.select('a[href]'):
            href = a_tag.get("href", "")
            # Match episode pages like /todo-no-tsumari-episode-02
            if not re.search(r'episode[-_]?\d', href, re.I):
                continue
            if "hentaistream.com" in href or href.startswith("/"):
                slug_match = re.search(r'hentaistream\.com/([^/]+)', href)
                slug = slug_match.group(1) if slug_match else href.strip("/").split("/")[-1]
                title = a_tag.get_text(strip=True) or slug.replace("-", " ").title()
                img_el = a_tag.select_one("img")
                cover = ""
                if img_el:
                    cover = img_el.get("src") or img_el.get("data-src") or ""
                    if cover and not cover.startswith("http"):
                        cover = HENTAISTREAM_DOMAIN + cover

                if title and slug:
                    results.append({
                        "title": title,
                        "slug": slug,
                        "cover": cover,
                        "views": "0",
                        "episode": _extract_episode(title),
                        "sub": 0, "dub": 0,
                        "total_episodes": 0, "type": "OVA", "rating": "",
                        "genres": [], "source": "hentaistream", "nsfw": True,
                    })

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r["slug"] not in seen:
                seen.add(r["slug"])
                unique.append(r)

        return {"results": unique[:24], "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"HentaiStream homepage error: {e}")
        return empty


@cached(300)
def hentaistream_search(query, page=1):
    """Search hentaistream.com via WordPress search."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(f"{HENTAISTREAM_DOMAIN}/", params={"s": query})
        if resp.status_code != 200:
            log.error(f"HentaiStream search {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for a_tag in soup.select('a[href]'):
            href = a_tag.get("href", "")
            if re.search(r'episode[-_]?\d', href, re.I):
                slug_match = re.search(r'hentaistream\.com/([^/]+)', href)
                slug = slug_match.group(1) if slug_match else href.strip("/").split("/")[-1]
                title = a_tag.get_text(strip=True) or slug.replace("-", " ").title()
                img_el = a_tag.select_one("img")
                cover = ""
                if img_el:
                    cover = img_el.get("src") or img_el.get("data-src") or ""
                    if cover and not cover.startswith("http"):
                        cover = HENTAISTREAM_DOMAIN + cover

                if title and slug:
                    results.append({
                        "title": title,
                        "slug": slug,
                        "cover": cover,
                        "views": "0",
                        "episode": _extract_episode(title),
                        "sub": 0, "dub": 0,
                        "total_episodes": 0, "type": "OVA", "rating": "",
                        "genres": [], "source": "hentaistream", "nsfw": True,
                    })

        seen = set()
        unique = []
        for r in results:
            if r["slug"] not in seen:
                seen.add(r["slug"])
                unique.append(r)

        return {"results": unique, "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"HentaiStream search error: {e}")
        return empty


@cached(600)
def hentaistream_detail(slug):
    """Get detail page from hentaistream."""
    try:
        resp = http_get(f"{HENTAISTREAM_DOMAIN}/{slug}")
        if resp.status_code != 200:
            log.error(f"HentaiStream detail {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title - clean special chars like ¤
        title_el = soup.select_one(".videotitle")
        if not title_el:
            title_el = soup.select_one("h1, h2")
        title = title_el.get_text(strip=True) if title_el else slug.replace("-", " ").title()
        # Remove special chars like ¤
        title = re.sub(r'[¤§¶]', '', title).strip()

        # Cover
        og_img = soup.select_one('meta[property="og:image"]')
        cover = og_img.get("content", "") if og_img else ""

        # Description
        desc_el = soup.select_one(".description, .videodetails p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Genres
        genres = []
        for genre_link in soup.select('a[href*="genres?genre="]'):
            genres.append(genre_link.get_text(strip=True))

        # Tags
        for tag_link in soup.select('.videotags a[href*="/list/"]'):
            tag_text = tag_link.get_text(strip=True)
            if tag_text and tag_text not in genres:
                genres.append(tag_text)

        # Views
        views_text = soup.get_text()
        views_match = re.search(r'Views?:\s*([\d,]+)', views_text, re.I)
        views = views_match.group(1).replace(",", "") if views_match else "0"

        # Stream URL - extract iframe src, fetch frame for direct MP4 with Referer
        stream_urls = []
        for iframe in soup.select("iframe[src]"):
            src = iframe.get("src", "")
            if src and ("frames" in src or "embed" in src or "player" in src):
                if not src.startswith("http"):
                    src = "https:" + src if src.startswith("//") else HENTAISTREAM_DOMAIN + src
                # Fetch frame page to extract direct MP4 URL
                try:
                    frame_resp = http_get(src, timeout=10)
                    if frame_resp.status_code == 200:
                        frame_soup = BeautifulSoup(frame_resp.text, "html.parser")
                        source_el = frame_soup.select_one("video source") or frame_soup.select_one("source[src]")
                        if not source_el:
                            source_el = frame_soup.select_one("video[src]")
                        if source_el:
                            mp4_url = source_el.get("src", "")
                            if mp4_url and mp4_url.startswith("http"):
                                stream_urls.append({"label": "HentaiStream", "url": mp4_url, "referer": HENTAISTREAM_DOMAIN + "/"})
                                break
                except Exception:
                    pass
                stream_urls.append({"label": "HentaiStream Embed", "url": src, "referer": HENTAISTREAM_DOMAIN + "/"})

        # Episode list from series page
        series_episodes = []
        series_link = soup.select_one('a[href*="hentaidvd/"]')
        if series_link:
            series_href = series_link.get("href", "")
            series_slug_match = re.search(r'hentaidvd/([^/]+)', series_href)
            if series_slug_match:
                series_slug = series_slug_match.group(1)
                try:
                    series_resp = http_get(f"{HENTAISTREAM_DOMAIN}/hentaidvd/{series_slug}")
                    if series_resp.status_code == 200:
                        series_soup = BeautifulSoup(series_resp.text, "html.parser")
                        for ep_link in series_soup.select('a[href*="episode"]'):
                            ep_href = ep_link.get("href", "")
                            ep_slug_match = re.search(r'hentaistream\.com/([^/]+)', ep_href)
                            ep_slug = ep_slug_match.group(1) if ep_slug_match else ep_href.strip("/").split("/")[-1]
                            ep_title = ep_link.get_text(strip=True)
                            if ep_slug and ep_title:
                                series_episodes.append({"title": ep_title, "slug": ep_slug})
                except Exception:
                    pass

        return {
            "title": title,
            "slug": slug,
            "cover": cover,
            "description": description,
            "views": views,
            "genres": genres,
            "stream_urls": stream_urls,
            "series_name": series_link.get_text(strip=True) if series_link else "",
            "series_episodes": series_episodes,
            "source": "hentaistream",
            "nsfw": True,
        }

    except Exception as e:
        log.error(f"HentaiStream detail error: {e}")
        return None


# ══════════════════════════════════════════════
# LATESTHENTAI.COM SCRAPER
# ══════════════════════════════════════════════

def _latesthentai_parse_card(item_el):
    """Parse a latesthentai.com card."""
    try:
        link = item_el.select_one("a[href*='/watch/']")
        if not link:
            link = item_el.select_one("a[href*='/serie/']")
        if not link:
            link = item_el.select_one("a")
        if not link:
            return None

        href = link.get("href", "")
        # Extract slug from /watch/slug/ or /serie/slug/
        slug_match = re.search(r'/(?:watch|serie)/([^/]+)/', href)
        slug = slug_match.group(1) if slug_match else href.strip("/").split("/")[-1]

        # Title
        title = ""
        h2 = link.select_one("h2, h3")
        if h2:
            title = h2.get_text(strip=True)

        if not title:
            img_el = link.select_one("img")
            if img_el:
                title = img_el.get("alt", "").strip()

        if not title:
            title = slug.replace("-", " ").title()

        # Cover
        cover = ""
        img_el = item_el.select_one("img")
        if img_el:
            cover = img_el.get("src") or img_el.get("data-src") or ""
            if cover and not cover.startswith("http"):
                cover = LATESTHENTAI_DOMAIN + cover

        # Views
        views = "0"
        full_text = item_el.get_text()
        vm = re.search(r'([\d,]+)\s*views?', full_text, re.I)
        if vm:
            views = vm.group(1).replace(",", "")

        # Brand/studio
        brand = ""
        brand_el = item_el.select_one("a[href*='/brand/']")
        if brand_el:
            brand = brand_el.get_text(strip=True)

        if not title or len(title) < 2:
            return None

        return {
            "title": title,
            "slug": slug,
            "cover": cover,
            "views": views,
            "episode": _extract_episode(title),
            "sub": 0, "dub": 0,
            "total_episodes": 0, "type": "OVA", "rating": "",
            "genres": [], "source": "latesthentai", "nsfw": True,
            "brand": brand,
        }
    except Exception as e:
        log.error(f"LatestHentai card parse error: {e}")
        return None


@cached(300)
def latesthentai_homepage(page=1):
    """Scrape latesthentai.com homepage."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(LATESTHENTAI_DOMAIN)
        if resp.status_code != 200:
            log.error(f"LatestHentai homepage {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # Parse all watch/episode links
        for a_tag in soup.select('a[href*="/watch/"]'):
            href = a_tag.get("href", "")
            slug_match = re.search(r'/watch/([^/]+)/', href)
            slug = slug_match.group(1) if slug_match else ""
            if not slug:
                continue

            title = ""
            h2 = a_tag.select_one("h2, h3")
            if h2:
                title = h2.get_text(strip=True)
            if not title:
                img = a_tag.select_one("img")
                title = img.get("alt", "").strip() if img else ""
            if not title:
                title = slug.replace("-", " ").title()

            img_el = a_tag.select_one("img")
            cover = ""
            if img_el:
                cover = img_el.get("src") or img_el.get("data-src") or ""
                if cover and not cover.startswith("http"):
                    cover = LATESTHENTAI_DOMAIN + cover

            if title and slug:
                results.append({
                    "title": title,
                    "slug": slug,
                    "cover": cover,
                    "views": "0",
                    "episode": _extract_episode(title),
                    "sub": 0, "dub": 0,
                    "total_episodes": 0, "type": "OVA", "rating": "",
                    "genres": [], "source": "latesthentai", "nsfw": True,
                })

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r["slug"] not in seen:
                seen.add(r["slug"])
                unique.append(r)

        return {"results": unique[:24], "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"LatestHentai homepage error: {e}")
        return empty


@cached(300)
def latesthentai_search(query, page=1):
    """Search latesthentai.com."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(f"{LATESTHENTAI_DOMAIN}/", params={"s": query})
        if resp.status_code != 200:
            log.error(f"LatestHentai search {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for a_tag in soup.select('a[href*="/watch/"]'):
            href = a_tag.get("href", "")
            slug_match = re.search(r'/watch/([^/]+)/', href)
            slug = slug_match.group(1) if slug_match else ""
            if not slug:
                continue

            title = ""
            h2 = a_tag.select_one("h2, h3")
            if h2:
                title = h2.get_text(strip=True)
            if not title:
                img = a_tag.select_one("img")
                title = img.get("alt", "").strip() if img else ""
            if not title:
                title = slug.replace("-", " ").title()

            img_el = a_tag.select_one("img")
            cover = ""
            if img_el:
                cover = img_el.get("src") or img_el.get("data-src") or ""
                if cover and not cover.startswith("http"):
                    cover = LATESTHENTAI_DOMAIN + cover

            if title and slug:
                results.append({
                    "title": title,
                    "slug": slug,
                    "cover": cover,
                    "views": "0",
                    "episode": _extract_episode(title),
                    "sub": 0, "dub": 0,
                    "total_episodes": 0, "type": "OVA", "rating": "",
                    "genres": [], "source": "latesthentai", "nsfw": True,
                })

        seen = set()
        unique = []
        for r in results:
            if r["slug"] not in seen:
                seen.add(r["slug"])
                unique.append(r)

        return {"results": unique, "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"LatestHentai search error: {e}")
        return empty


@cached(600)
def latesthentai_detail(slug):
    """Get detail page from latesthentai."""
    try:
        resp = http_get(f"{LATESTHENTAI_DOMAIN}/watch/{slug}/")
        if resp.status_code != 200:
            # Try as series page
            resp = http_get(f"{LATESTHENTAI_DOMAIN}/serie/{slug}/")
            if resp.status_code != 200:
                log.error(f"LatestHentai detail {resp.status_code}")
                return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title - use og:title for cleanest result
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            title = og_title.get("content", "").replace(" - Free Hentai", "").strip()
        else:
            title_el = soup.select_one("h1")
            title = title_el.get_text(strip=True) if title_el else slug.replace("-", " ").title()

        # Cover
        og_img = soup.select_one('meta[property="og:image"]')
        cover = og_img.get("content", "") if og_img else ""

        # Description
        desc_el = soup.select_one(".entry-content p, .description")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Genres/tags
        genres = []
        for tag_link in soup.select('a[href*="/genre/"]'):
            genres.append(tag_link.get_text(strip=True))

        # Views
        views_text = soup.get_text()
        views_match = re.search(r'([\d,]+)\s*views', views_text, re.I)
        views = views_match.group(1).replace(",", "") if views_match else "0"

        # Brand
        brand_el = soup.select_one('a[href*="/brand/"]')
        brand = brand_el.get_text(strip=True) if brand_el else ""

        # Stream URL - prefer nhplayer iframe (it handles CDN auth internally)
        stream_urls = []
        for iframe in soup.select("iframe[src]"):
            src = iframe.get("src", "")
            if not src or "about:blank" in src or len(src) < 10:
                continue
            if "adtng.com" in src or "ad" in src.lower():
                continue
            if not src.startswith("http"):
                src = "https:" + src if src.startswith("//") else LATESTHENTAI_DOMAIN + src
            # Return the nhplayer iframe URL - it handles CDN auth/cookies internally
            # Do NOT decode base64 to raw CDN URLs as they require nhplayer context
            stream_urls.append({"label": "Player", "url": src})
            break

        return {
            "title": title,
            "slug": slug,
            "cover": cover,
            "description": description,
            "views": views,
            "genres": genres,
            "stream_urls": stream_urls,
            "series_name": brand,
            "series_episodes": [],
            "source": "latesthentai",
            "nsfw": True,
        }

    except Exception as e:
        log.error(f"LatestHentai detail error: {e}")
        return None


# ══════════════════════════════════════════════
# HENTAIYES.COM SCRAPER
# ══════════════════════════════════════════════

def _hentaiyes_parse_card(item_el):
    """Parse a hentaiyes.com card."""
    try:
        link = item_el.select_one("a[href*='/watch/']")
        if not link:
            link = item_el.select_one("a[href*='/series/']")
        if not link:
            link = item_el.select_one("a")
        if not link:
            return None

        href = link.get("href", "")
        # Extract slug from /watch/slug/ or /series/slug/
        slug_match = re.search(r'/(?:watch|series)/([^/]+)/', href)
        slug = slug_match.group(1) if slug_match else href.strip("/").split("/")[-1]

        # Title
        title = ""
        h6 = link.select_one("h6, h5, h4")
        if h6:
            title = h6.get_text(strip=True)

        if not title:
            img_el = link.select_one("img")
            if img_el:
                title = img_el.get("alt", "").strip()

        if not title:
            title = slug.replace("-", " ").title()

        # Cover
        cover = ""
        img_el = item_el.select_one("img")
        if img_el:
            cover = img_el.get("data-src") or img_el.get("src") or ""
            if cover and not cover.startswith("http"):
                cover = HENTAIYES_DOMAIN + cover

        # Views
        views = "0"
        full_text = item_el.get_text()
        vm = re.search(r'([\d,]+)', full_text)
        if vm:
            views = vm.group(1).replace(",", "")

        # Quality
        quality = ""
        q_el = item_el.select_one("h6")
        if q_el:
            quality = q_el.get_text(strip=True)

        if not title or len(title) < 2:
            return None

        return {
            "title": title,
            "slug": slug,
            "cover": cover,
            "views": views,
            "episode": _extract_episode(title),
            "sub": 0, "dub": 0,
            "total_episodes": 0, "type": "OVA", "rating": "",
            "genres": [], "source": "hentaiyes", "nsfw": True,
            "quality": quality,
        }
    except Exception as e:
        log.error(f"HentaiYes card parse error: {e}")
        return None


@cached(300)
def hentaiyes_homepage(page=1):
    """Scrape hentaiyes.com homepage."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(HENTAIYES_DOMAIN)
        if resp.status_code != 200:
            log.error(f"HentaiYes homepage {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # Parse all watch/episode links
        for a_tag in soup.select('a[href*="/watch/"]'):
            href = a_tag.get("href", "")
            slug_match = re.search(r'/watch/([^/]+)/', href)
            slug = slug_match.group(1) if slug_match else ""
            if not slug:
                continue

            title = ""
            h6 = a_tag.select_one("h6")
            if h6:
                title = h6.get_text(strip=True)
            if not title:
                img = a_tag.select_one("img")
                title = img.get("alt", "").strip() if img else ""
            if not title:
                title = slug.replace("-", " ").title()

            img_el = a_tag.select_one("img")
            cover = ""
            if img_el:
                cover = img_el.get("data-src") or img_el.get("src") or ""
                if cover and not cover.startswith("http"):
                    cover = HENTAIYES_DOMAIN + cover

            if title and slug:
                results.append({
                    "title": title,
                    "slug": slug,
                    "cover": cover,
                    "views": "0",
                    "episode": _extract_episode(title),
                    "sub": 0, "dub": 0,
                    "total_episodes": 0, "type": "OVA", "rating": "",
                    "genres": [], "source": "hentaiyes", "nsfw": True,
                })

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r["slug"] not in seen:
                seen.add(r["slug"])
                unique.append(r)

        return {"results": unique[:24], "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"HentaiYes homepage error: {e}")
        return empty


@cached(300)
def hentaiyes_search(query, page=1):
    """Search hentaiyes.com."""
    empty = {"results": [], "total_pages": 1, "current_page": page}
    try:
        resp = http_get(f"{HENTAIYES_DOMAIN}/search/{query.replace(' ', '+')}/")
        if resp.status_code != 200:
            log.error(f"HentaiYes search {resp.status_code}")
            return empty

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for a_tag in soup.select('a[href*="/watch/"]'):
            href = a_tag.get("href", "")
            slug_match = re.search(r'/watch/([^/]+)/', href)
            slug = slug_match.group(1) if slug_match else ""
            if not slug:
                continue

            title = ""
            h6 = a_tag.select_one("h6")
            if h6:
                title = h6.get_text(strip=True)
            if not title:
                img = a_tag.select_one("img")
                title = img.get("alt", "").strip() if img else ""
            if not title:
                title = slug.replace("-", " ").title()

            img_el = a_tag.select_one("img")
            cover = ""
            if img_el:
                cover = img_el.get("data-src") or img_el.get("src") or ""
                if cover and not cover.startswith("http"):
                    cover = HENTAIYES_DOMAIN + cover

            if title and slug:
                results.append({
                    "title": title,
                    "slug": slug,
                    "cover": cover,
                    "views": "0",
                    "episode": _extract_episode(title),
                    "sub": 0, "dub": 0,
                    "total_episodes": 0, "type": "OVA", "rating": "",
                    "genres": [], "source": "hentaiyes", "nsfw": True,
                })

        seen = set()
        unique = []
        for r in results:
            if r["slug"] not in seen:
                seen.add(r["slug"])
                unique.append(r)

        return {"results": unique, "total_pages": 1, "current_page": page}

    except Exception as e:
        log.error(f"HentaiYes search error: {e}")
        return empty


@cached(600)
def hentaiyes_detail(slug):
    """Get detail page from hentaiyes."""
    try:
        resp = http_get(f"{HENTAIYES_DOMAIN}/watch/{slug}/")
        if resp.status_code != 200:
            log.error(f"HentaiYes detail {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title - use og:title for cleanest result
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            title = og_title.get("content", "").replace(" | HD Stream | HentaiYes", "").strip()
        else:
            # Fallback: look for specific title elements, skip nav
            title_el = soup.select_one(".post-title h4, .post-title h3, .singlePostStats h4")
            if not title_el:
                title_el = soup.select_one("h4.post-title, h3.post-title")
            if title_el:
                title = title_el.get_text(strip=True)
            else:
                title = slug.replace("-", " ").title()

        # Cover
        og_img = soup.select_one('meta[property="og:image"]')
        cover = og_img.get("content", "") if og_img else ""

        # Description
        desc_el = soup.select_one(".description p, .description")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Genres/tags
        genres = []
        for tag_link in soup.select('.tags a[href*="/tag/"]'):
            genres.append(tag_link.get_text(strip=True))

        # Views
        views_text = soup.get_text()
        views_match = re.search(r'([\d,]+)', views_text)
        views = views_match.group(1).replace(",", "") if views_match else "0"

        # Stream URL - extract embed iframe, fetch for direct MP4 with Referer
        stream_urls = []
        for iframe in soup.select("iframe[src]"):
            src = iframe.get("src", "")
            if src and "about:blank" not in src and len(src) > 10:
                if src.startswith("//"):
                    src = "https:" + src
                elif not src.startswith("http"):
                    src = HENTAIYES_DOMAIN + src
                # Fetch embed page to extract direct video URL
                try:
                    embed_resp = http_get(src, timeout=10)
                    if embed_resp.status_code == 200:
                        embed_soup = BeautifulSoup(embed_resp.text, "html.parser")
                        source_el = embed_soup.select_one("video source") or embed_soup.select_one("source[src]")
                        if not source_el:
                            source_el = embed_soup.select_one("video[src]")
                        if source_el:
                            vid_url = source_el.get("src", "")
                            if vid_url and vid_url.startswith("http"):
                                # Determine referer from embed URL domain
                                embed_domain = urlparse(src)
                                embed_referer = f"{embed_domain.scheme}://{embed_domain.netloc}/"
                                stream_urls.append({"label": "HentaiYes", "url": vid_url, "referer": embed_referer})
                                break
                        # Also check for JS player file param
                        file_match = re.search(r'file\s*:\s*["\']?(https?://[^"\'>\s]+\.(mp4|m3u8)[^"\'>\s]*)', embed_resp.text)
                        if file_match:
                            embed_domain = urlparse(src)
                            embed_referer = f"{embed_domain.scheme}://{embed_domain.netloc}/"
                            stream_urls.append({"label": "HentaiYes", "url": file_match.group(1), "referer": embed_referer})
                            break
                except Exception:
                    pass
                stream_urls.append({"label": "HentaiYes Embed", "url": src, "referer": HENTAIYES_DOMAIN + "/"})
                break

        # Series info
        series_el = soup.select_one('.categories a[href*="/series/"]')
        series_name = series_el.get_text(strip=True) if series_el else ""

        return {
            "title": title,
            "slug": slug,
            "cover": cover,
            "description": description,
            "views": views,
            "genres": genres,
            "stream_urls": stream_urls,
            "series_name": series_name,
            "series_episodes": [],
            "source": "hentaiyes",
            "nsfw": True,
        }

    except Exception as e:
        log.error(f"HentaiYes detail error: {e}")
        return None


# ══════════════════════════════════════════════
# COMBINED ENDPOINTS (for API routing)
# ══════════════════════════════════════════════

def nsfw_homepage():
    """Combined homepage from all 5 sources."""
    all_results = []

    def _fetch(label, fn):
        try:
            return fn()
        except Exception as e:
            log.error(f"nsfw_homepage {label} error: {e}")
            return {}

    # Fetch all concurrently
    from concurrent.futures import ThreadPoolExecutor, as_completed
    fns = {
        "hanime": hanime_homepage,
        "ohentai": ohentai_homepage,
        "hentaistream": hentaistream_homepage,
        "latesthentai": latesthentai_homepage,
        "hentaiyes": hentaiyes_homepage,
    }
    results_map = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        future_map = {ex.submit(_fetch, k, v): k for k, v in fns.items()}
        for fut in as_completed(future_map, timeout=60):
            name = future_map[fut]
            try:
                results_map[name] = fut.result(timeout=5)
            except Exception as e:
                log.error(f"nsfw_homepage future {name}: {e}")
                results_map[name] = {}

    hanime_data = results_map.get("hanime", {})
    ohentai_data = results_map.get("ohentai", {})
    hentaistream_data = results_map.get("hentaistream", {})
    latesthentai_data = results_map.get("latesthentai", {})
    hentaiyes_data = results_map.get("hentaiyes", {})

    log.info(f"nsfw_homepage: hanime={len(hanime_data.get('recent',[]))} ohentai={len(ohentai_data.get('results',[]))} hstream={len(hentaistream_data.get('results',[]))} lhentai={len(latesthentai_data.get('results',[]))} hyes={len(hentaiyes_data.get('results',[]))}")

    # Interleave results from all sources
    all_recent = []
    all_results_lists = [
        hentaistream_data.get("results", []),
        latesthentai_data.get("results", []),
        hentaiyes_data.get("results", []),
        ohentai_data.get("results", []),
        hanime_data.get("recent", []),
    ]
    # Round-robin interleave
    max_len = max(len(lst) for lst in all_results_lists) if all_results_lists else 0
    seen_slugs = set()
    for i in range(max_len):
        for lst in all_results_lists:
            if i < len(lst):
                item = lst[i]
                slug = item.get("slug", "")
                if slug and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    all_recent.append(item)

    all_trending = []
    for item in hanime_data.get("trending", []):
        all_trending.append(item)
    for item in hentaistream_data.get("results", [])[:10]:
        slug = item.get("slug", "")
        if slug not in seen_slugs:
            all_trending.append(item)
            seen_slugs.add(slug)

    return {
        "trending": all_trending[:20] or all_recent[:20],
        "recent": all_recent[:24],
        "upcoming": [],
        "new_release": all_recent[:12],
        "new_added": all_recent[:12],
        "completed": hanime_data.get("completed", []),
        "top_anime": all_trending[:9] or all_recent[:9],
    }


def nsfw_search(query, page=1):
    """Search across all 5 sources."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []

    def safe_search(fn, query, page):
        try:
            return fn(query, page)
        except Exception as e:
            log.error(f"nsfw_search error: {e}")
            return {"results": []}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(safe_search, ohentai_search, query, page),
            executor.submit(safe_search, hentaistream_search, query, page),
            executor.submit(safe_search, latesthentai_search, query, page),
            executor.submit(safe_search, hentaiyes_search, query, page),
        ]
        for future in as_completed(futures):
            try:
                data = future.result(timeout=30)
                results.extend(data.get("results", []))
            except Exception as e:
                log.error(f"nsfw_search future error: {e}")

    return {
        "results": results,
        "total": len(results),
        "has_next": False,
    }


def nsfw_trending():
    """Get trending from hanime + others."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []

    def safe_call(fn):
        try:
            return fn()
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(lambda: safe_call(lambda: hanime_trending("monthly").get("results", [])[:20])),
            executor.submit(lambda: safe_call(lambda: hentaistream_homepage().get("results", [])[:10])),
        ]
        for future in as_completed(futures):
            try:
                items = future.result(timeout=30)
                if isinstance(items, list):
                    results.extend(items)
            except Exception:
                pass

    return {"results": results[:20]}


def nsfw_recent():
    """Get recent uploads from all sources."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []

    def safe_call(fn):
        try:
            return fn()
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(lambda: safe_call(lambda: hanime_homepage().get("recent", [])[:12])),
            executor.submit(lambda: safe_call(lambda: hentaistream_homepage().get("results", [])[:8])),
            executor.submit(lambda: safe_call(lambda: latesthentai_homepage().get("results", [])[:8])),
            executor.submit(lambda: safe_call(lambda: hentaiyes_homepage().get("results", [])[:8])),
        ]
        for future in as_completed(futures):
            try:
                items = future.result(timeout=30)
                if isinstance(items, list):
                    results.extend(items)
            except Exception:
                pass
    return {"results": results[:24]}


def nsfw_new_release():
    """Get new releases."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []

    def safe_call(fn):
        try:
            return fn()
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(lambda: safe_call(lambda: hanime_homepage().get("new_release", [])[:12])),
            executor.submit(lambda: safe_call(lambda: hentaistream_homepage().get("results", [])[:6])),
            executor.submit(lambda: safe_call(lambda: latesthentai_homepage().get("results", [])[:6])),
        ]
        for future in as_completed(futures):
            try:
                items = future.result(timeout=30)
                if isinstance(items, list):
                    results.extend(items)
            except Exception:
                pass
    return {"results": results[:12]}


def nsfw_new_added():
    """Get newly added."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []

    def safe_call(fn):
        try:
            return fn()
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(lambda: safe_call(lambda: hanime_homepage().get("new_added", [])[:12])),
            executor.submit(lambda: safe_call(lambda: hentaiyes_homepage().get("results", [])[:6])),
        ]
        for future in as_completed(futures):
            try:
                items = future.result(timeout=30)
                if isinstance(items, list):
                    results.extend(items)
            except Exception:
                pass
    return {"results": results[:12]}


def nsfw_completed():
    """Get completed series."""
    data = hanime_homepage()
    return {"results": data.get("completed", [])[:12]}


def nsfw_top():
    """Get top rated from all sources."""
    results = []
    try:
        data = hanime_trending("monthly")
        results.extend(data.get("results", [])[:9])
    except Exception:
        pass
    if len(results) < 9:
        try:
            data = hentaistream_homepage()
            results.extend(data.get("results", [])[:9 - len(results)])
        except Exception:
            pass
    return {"results": results[:9]}


def _title_from_slug(slug):
    """Extract a clean search title from any slug (hanime or other)."""
    clean = re.sub(r'[-_]episode[-_]\d+$', '', slug, flags=re.I)
    clean = re.sub(r'[-_]ep[-_]?\d+$', '', clean, flags=re.I)
    clean = re.sub(r'-[a-z0-9]{5}$', '', clean)
    return clean.replace('-', ' ').replace('_', ' ').strip()


def _fuzzy_match(query, candidate):
    """Check if a candidate title reasonably matches the query."""
    q = query.lower().strip()
    c = candidate.lower().strip()
    if q == c:
        return True
    if q in c or c in q:
        return True
    # Check if first 60% of words match
    qw = q.split()
    cw = c.split()
    if not qw:
        return False
    matches = sum(1 for w in qw if any(w in cw2 for cw2 in cw))
    return matches >= len(qw) * 0.5


def _search_all_sources_by_title(title):
    """Search all 4 non-hanime sources by title, return all results sorted by relevance."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if not title or len(title) < 3:
        return []

    def _try_search(label, fn):
        try:
            data = fn(title, page=1)
            results = data.get("results", []) if data else []
            return [(label, r) for r in results[:5] if _fuzzy_match(title, r.get("title", ""))]
        except Exception:
            pass
        return []

    all_results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [
            ex.submit(_try_search, "hentaistream", hentaistream_search),
            ex.submit(_try_search, "hentaiyes", hentaiyes_search),
            ex.submit(_try_search, "latesthentai", latesthentai_search),
            ex.submit(_try_search, "ohentai", ohentai_search),
        ]
        for fut in as_completed(futures, timeout=20):
            try:
                all_results.extend(fut.result(timeout=5))
            except Exception:
                pass
    return all_results


def nsfw_detail(slug):
    """Get detail — metadata from best available source, streams from ALL sources."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 1) Get metadata from first available source (slug-based)
    meta = None
    resolved_slug = slug
    if re.match(r'^[A-Za-z0-9+/=]{4,}$', slug):
        meta = ohentai_detail(slug)
    if not meta:
        meta = hentaistream_detail(slug)
    if not meta:
        meta = hentaiyes_detail(slug)
    if not meta:
        meta = latesthentai_detail(slug)

    # 2) If slug-based lookup failed, search by title (for hanime slugs etc.)
    if not meta:
        title = _title_from_slug(slug)
        search_results = _search_all_sources_by_title(title)
        for label, result in search_results:
            result_slug = result.get("slug", "")
            if result_slug and result_slug != slug:
                inner = nsfw_detail(result_slug)
                if inner:
                    meta = inner
                    resolved_slug = result_slug
                    break

    if not meta:
        return None

    # 3) Collect stream URLs from ALL sources (using resolved slug + title fallback)
    all_streams = list(meta.get("stream_urls", []))
    seen_urls = {s["url"] for s in all_streams}

    def _get_streams(label, fn, search_fn, slug_val):
        try:
            result = fn(slug_val)
            if result and result.get("stream_urls"):
                return result["stream_urls"]
        except Exception:
            pass
        # Fallback: search by title if slug didn't work
        raw_title = meta.get("title", "")
        if raw_title and search_fn:
            # Try progressively shorter titles for better search matches
            clean_title = re.sub(r'\s+Season\s+\d+$', '', raw_title, flags=re.I).strip()
            clean_title = re.sub(r'\s+Part\s+\d+$', '', clean_title, flags=re.I).strip()
            for try_title in [raw_title, clean_title]:
                if not try_title or len(try_title) < 5:
                    continue
                try:
                    data = search_fn(try_title, page=1)
                    results = (data.get("results", []) if data else [])[:5]
                    for r in results:
                        if _fuzzy_match(try_title, r.get("title", "")):
                            r_slug = r.get("slug", "")
                            if r_slug:
                                r_detail = fn(r_slug)
                                if r_detail and r_detail.get("stream_urls"):
                                    return r_detail["stream_urls"]
                except Exception:
                    pass
        return []

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = []
        if re.match(r'^[A-Za-z0-9+/=]{4,}$', resolved_slug):
            futures.append(ex.submit(_get_streams, "ohentai", ohentai_detail, ohentai_search, resolved_slug))
        futures.append(ex.submit(_get_streams, "hentaistream", hentaistream_detail, hentaistream_search, resolved_slug))
        futures.append(ex.submit(_get_streams, "hentaiyes", hentaiyes_detail, hentaiyes_search, resolved_slug))
        futures.append(ex.submit(_get_streams, "latesthentai", latesthentai_detail, latesthentai_search, resolved_slug))

        for fut in as_completed(futures, timeout=30):
            try:
                streams = fut.result(timeout=5)
                for s in streams:
                    if s["url"] not in seen_urls:
                        seen_urls.add(s["url"])
                        all_streams.append(s)
            except Exception:
                pass

    meta["stream_urls"] = all_streams
    meta["resolved_slug"] = resolved_slug
    return meta


def nsfw_stream(slug):
    """Get stream URL for a video."""
    detail = nsfw_detail(slug)
    if detail and detail.get("stream_urls"):
        return detail["stream_urls"][0].get("url", "")
    return ""
