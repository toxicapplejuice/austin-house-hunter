"""Pool detection from listing photos using Claude vision.

The listings API exposes no pool field, but it returns each home's photos for
free. Pools are a top selling feature and are almost always photographed, so a
quick vision pass over a sample of the photos is a reliable pool gate. The caller
fails CLOSED: anything not confirmed pool-free (True or None) is dropped.
"""

import base64
import json
import os
import re
from typing import Any

import requests

try:  # anthropic is only needed at call time, not import time
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

# Cheap, fast, vision-capable — right tier for high-volume photo classification.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_PROMPT = (
    "These are photos of ONE residential property for sale. Decide whether the "
    "property has its OWN swimming pool (in-ground or above-ground) on its lot. "
    "Ignore community pools, neighbors' pools, and tiny pools far in the distance. "
    'Reply with ONLY a JSON object: {"verdict": "pool" | "no_pool" | "unsure", '
    '"evidence": "<=10 words"}. Use "no_pool" only when the photos give a '
    'reasonable view of the yard/exterior and show none; use "unsure" if you '
    "cannot tell (e.g. interior photos only)."
)


def _sample(photo_urls: list[str] | None, max_photos: int) -> list[str]:
    """Evenly sample up to ``max_photos`` across the set so coverage spans front,
    back, aerial and interior shots (a pool can appear anywhere in the gallery)."""
    photos = [u for u in (photo_urls or []) if u]
    if len(photos) <= max_photos:
        return photos
    step = len(photos) / max_photos
    return [photos[int(i * step)] for i in range(max_photos)]


def parse_verdict(text: str) -> tuple[bool | None, str]:
    """Map the model's reply to (has_pool, reason). Pure — unit-tested.

    pool -> True, no_pool -> False, unsure/unparseable -> None (caller fails closed).
    """
    if not text:
        return None, "empty response"
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        obj = json.loads(match.group(0) if match else text)
        verdict = str(obj.get("verdict", "")).lower().strip()
        evidence = str(obj.get("evidence", ""))[:80]
    except Exception:  # noqa: BLE001 — fall back to keyword scan
        low = text.lower()
        if "no_pool" in low or "no pool" in low:
            return False, "text:no_pool"
        if "pool" in low:
            return True, "text:pool"
        return None, "unparseable"
    if verdict == "pool":
        return True, f"vision:pool ({evidence})"
    if verdict == "no_pool":
        return False, f"vision:no_pool ({evidence})"
    return None, f"vision:unsure ({evidence})"


def _image_block(url: str, timeout: int) -> dict[str, Any] | None:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        media_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        if media_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            media_type = "image/jpeg"
        data = base64.standard_b64encode(resp.content).decode("ascii")
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
    except Exception:  # noqa: BLE001
        return None


def detect_pool_from_photos(
    photo_urls: list[str] | None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    max_photos: int = 6,
    timeout: int = 30,
) -> tuple[bool | None, str]:
    """Return (has_pool, reason): True if a pool is visible, False if clearly none,
    None if undetermined (no photos / no key / SDK missing / API error). The caller
    fails closed on None."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if anthropic is None:
        return None, "anthropic SDK not installed"
    if not api_key:
        return None, "no ANTHROPIC_API_KEY"

    sampled = _sample(photo_urls, max_photos)
    if not sampled:
        return None, "no photos"
    blocks = [b for b in (_image_block(u, timeout) for u in sampled) if b]
    if not blocks:
        return None, "no images fetched"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=80,
            messages=[{"role": "user", "content": blocks + [{"type": "text", "text": _PROMPT}]}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception as e:  # noqa: BLE001
        return None, f"vision API error: {e}"
    return parse_verdict(text)
