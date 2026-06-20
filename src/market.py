import logging
import re
import threading
import urllib.request
import urllib.parse
import os
from io import BytesIO

logger = logging.getLogger("Evera")

BASE_URL = "https://motionbgs.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
}

THUMB_SIZES = {
    "small": "/i/c/364x205/",
    "large": "/i/c/546x308/",
}


def _fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def _fetch_bytes(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def parse_wallpapers(html):
    items = []
    pattern = re.compile(
        r'<a\s+title="([^"]*)"\s+href=/([^"\s>]+)[^>]*>.*?'
        r'<img[^>]*src=([^"\s>]+)[^>]*>.*?'
        r'<span\s+class=frm>([^<]*)</span>',
        re.DOTALL
    )
    for match in pattern.finditer(html):
        title, slug, thumb, fmt = match.groups()
        if not thumb.startswith("http"):
            thumb = BASE_URL + thumb
        items.append({
            "title": title.strip(),
            "slug": slug.strip("/"),
            "thumb": thumb,
            "format": fmt.strip(),
        })
    return items


def fetch_latest(page=1):
    url = f"{BASE_URL}/" if page == 1 else f"{BASE_URL}/{page}/"
    try:
        html = _fetch(url)
        return parse_wallpapers(html)
    except Exception as e:
        logger.error(f"[Market] Failed to fetch latest: {e}")
        return []


def search(query, page=1):
    params = urllib.parse.urlencode({"q": query})
    url = f"{BASE_URL}/search?{params}"
    if page > 1:
        url += f"&page={page}"
    try:
        html = _fetch(url)
        return parse_wallpapers(html)
    except Exception as e:
        logger.error(f"[Market] Search failed: {e}")
        return []


def fetch_by_tag(tag, page=1):
    url = f"{BASE_URL}/tag:{tag}/"
    if page > 1:
        url = f"{BASE_URL}/tag:{tag}/{page}/"
    try:
        html = _fetch(url)
        return parse_wallpapers(html)
    except Exception as e:
        logger.error(f"[Market] Failed to fetch tag '{tag}': {e}")
        return []


def fetch_thumb_bytes(url):
    try:
        return _fetch_bytes(url)
    except Exception as e:
        logger.error(f"[Market] Failed to fetch thumbnail: {e}")
        return None


def get_download_url(slug):
    url = f"{BASE_URL}/{slug}"
    try:
        html = _fetch(url)
        pattern = re.compile(
            r'<meta\s+[^>]*content=(https?://[^"\'<>\s]+media/(\d+)/[^"\'<>\s]+\.(?:mp4|webm))[^>]*property=og:video',
            re.IGNORECASE
        )
        match = pattern.search(html)
        if match:
            video_id = match.group(2)
            return f"{BASE_URL}/dl/4k/{video_id}"
        pattern2 = re.compile(
            r'<meta\s+[^>]*property=og:video[^>]*content=(https?://[^"\'<>\s]+media/(\d+)/[^"\'<>\s]+\.(?:mp4|webm))',
            re.IGNORECASE
        )
        match2 = pattern2.search(html)
        if match2:
            video_id = match2.group(2)
            return f"{BASE_URL}/dl/4k/{video_id}"
        return None
    except Exception as e:
        logger.error(f"[Market] Failed to get download URL for '{slug}': {e}")
        return None


def download_video(url, dest_path):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
        return True
    except Exception as e:
        logger.error(f"[Market] Failed to download video: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


# ---- Moewalls.com ----

MOEWALLS_BASE = "https://moewalls.com"
MOEWALLS_DL_BASE = "https://go.moewalls.com"


def parse_moewalls_wallpapers(html):
    items = []
    pattern = re.compile(
        r'<a\s+title="([^"]*)"\s+class="g1-frame"\s+href="https://moewalls\.com/([^"]+)"',
        re.DOTALL
    )
    for match in pattern.finditer(html):
        title, path = match.groups()
        slug = path.strip("/")
        items.append({"title": title.strip(), "slug": slug, "thumb": None, "format": "HD"})
    for item in items:
        slug_part = item["slug"].rsplit("/", 1)[-1].replace("-live-wallpaper", "")
        thumb_pattern = re.compile(
            rf'https://moewalls\.com/wp-content/uploads/\d+/\d+/{re.escape(slug_part)}-thumb-\d+x\d+\.jpg',
            re.IGNORECASE
        )
        m = thumb_pattern.search(html)
        if m:
            item["thumb"] = m.group(0)
    return items


def fetch_moewalls_latest(page=1):
    url = MOEWALLS_BASE if page == 1 else f"{MOEWALLS_BASE}/page/{page}/"
    try:
        html = _fetch(url)
        return parse_moewalls_wallpapers(html)
    except Exception as e:
        logger.error(f"[Market] MoeWalls latest failed: {e}")
        return []


def fetch_moewalls_by_category(category, page=1):
    url = f"{MOEWALLS_BASE}/category/{category}/"
    if page > 1:
        url = f"{MOEWALLS_BASE}/category/{category}/page/{page}/"
    try:
        html = _fetch(url)
        return parse_moewalls_wallpapers(html)
    except Exception as e:
        logger.error(f"[Market] MoeWalls category '{category}' failed: {e}")
        return []


def search_moewalls(query, page=1):
    params = urllib.parse.urlencode({"s": query})
    url = f"{MOEWALLS_BASE}/?{params}"
    if page > 1:
        url += f"&page={page}"
    try:
        html = _fetch(url)
        return parse_moewalls_wallpapers(html)
    except Exception as e:
        logger.error(f"[Market] MoeWalls search failed: {e}")
        return []


def get_moewalls_download_url(slug):
    url = f"{MOEWALLS_BASE}/{slug}/"
    try:
        html = _fetch(url)
        m = re.search(r'id="moe-download"[^>]*data-url="([^"]+)"', html)
        if m:
            return f"{MOEWALLS_DL_BASE}/download.php?video={m.group(1)}"
        return None
    except Exception as e:
        logger.error(f"[Market] MoeWalls download URL for '{slug}' failed: {e}")
        return None
