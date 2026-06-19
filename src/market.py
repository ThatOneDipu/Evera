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
        r'<a\s+title="([^"]*)"\s+href="/([^"]+)"[^>]*>.*?'
        r'<img[^>]*src="([^"]+)"[^>]*>.*?'
        r'<span\s+class="frm">([^<]*)</span>',
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
    url = f"{BASE_URL}/search/?{params}"
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
    url = f"{BASE_URL}/{slug}/"
    try:
        html = _fetch(url)
        pattern = re.compile(
            r'<a\s+[^>]*href="(https?://[^"]+\.(mp4|webm))"',
            re.IGNORECASE
        )
        match = pattern.search(html)
        if match:
            return match.group(1)
        pattern2 = re.compile(
            r'data-url\s*=\s*["\']([^"\']+\.(mp4|webm))',
            re.IGNORECASE
        )
        match2 = pattern2.search(html)
        if match2:
            return match2.group(1)
        pattern3 = re.compile(
            r'<source\s+[^>]*src="([^"]+\.(mp4|webm))"',
            re.IGNORECASE
        )
        match3 = pattern3.search(html)
        if match3:
            return match3.group(1)
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
