#!/usr/bin/env python3
from __future__ import annotations
"""Browse Leewow customizable product templates.

Default output is a Feishu-friendly Markdown table so OpenClaw can render the
result inside an interactive card with an image column. `--json` is kept for
debugging / compatibility.
"""

import argparse
import hashlib
import json
import os
import sys
from urllib.parse import urlparse

# Load environment variables from ~/.openclaw/.env
def _load_env_file():
    env_path = os.path.expanduser("~/.openclaw/.env")
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key not in os.environ:
                        os.environ[key] = value

_load_env_file()

import requests
from claw_auth import claw_get

CLAW_BASE_URL = os.getenv("CLAW_BASE_URL", "https://leewow.com")
CLAW_PATH_PREFIX = os.getenv("CLAW_PATH_PREFIX", "")
CLAW_SK = os.getenv("CLAW_SK", "")

WORKSPACE_DIR = os.path.expanduser("~/.openclaw/workspace")
TEMPLATE_IMG_DIR = os.path.join(WORKSPACE_DIR, "template_images")


def _download_cover_image(remote_url: str, template_id) -> str | None:
    """Download template cover image to workspace and return local path.

    Uses a content-hash filename so repeated calls are instant (cache hit).
    Returns None on failure — caller should fall back to remote URL.
    """
    if not remote_url:
        return None
    try:
        os.makedirs(TEMPLATE_IMG_DIR, exist_ok=True)
        url_hash = hashlib.md5(remote_url.encode()).hexdigest()[:10]
        parsed = urlparse(remote_url)
        ext = os.path.splitext(parsed.path)[1] or ".jpg"
        filename = f"template_{template_id}_{url_hash}{ext}"
        filepath = os.path.join(TEMPLATE_IMG_DIR, filename)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath

        resp = requests.get(remote_url, timeout=15)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath
    except Exception as e:
        print(f"Warning: failed to download cover image: {e}", file=sys.stderr)
        return None


def _fetch_templates(category: str = None, count: int = 5) -> list:
    if not CLAW_SK:
        return [{"error": "CLAW_SK environment variable is not set."}]

    count = min(max(count, 1), 10)
    url = f"{CLAW_BASE_URL}{CLAW_PATH_PREFIX}/claw/templates"

    try:
        resp = claw_get(CLAW_SK, url, timeout=15)
        data = resp.json()
    except Exception as e:
        return [{"error": f"Failed to fetch templates: {e}"}]

    if data.get("code") != 0:
        return [{"error": f"API returned: {data.get('message', 'Unknown error')}"}]

    templates = data.get("data", [])

    if category:
        cat_lower = category.lower()
        templates = [
            t for t in templates
            if cat_lower in (t.get("name", "") + t.get("description", "")).lower()
        ]

    return templates[:count]


def _extract_price(sku_configs) -> str:
    if not sku_configs:
        return ""
    try:
        skus = json.loads(sku_configs) if isinstance(sku_configs, str) else sku_configs
        if isinstance(skus, list) and skus:
            first = skus[0]
            price = first.get("priceOnSell") or first.get("price")
            origin = first.get("originPrice")
            currency = first.get("currency", "USD")
            if price:
                s = f"**${price} {currency}**"
                if origin and float(origin) > float(price):
                    s += f" ~~${origin}~~"
                return s
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return ""


def _normalize_plain_text(value) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _escape_table_cell(value) -> str:
    text = _normalize_plain_text(value)
    if not text:
        return "-"
    return text.replace("|", "\\|")


def _compact_description(value: str, limit: int = 56) -> str:
    text = _normalize_plain_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_image_cell(name: str, cover_url: str) -> str:
    if not cover_url:
        return "-"
    alt = _escape_table_cell(name or "Preview")
    return f"![{alt}]({cover_url})"


def _format_preview_link(cover_url: str) -> str:
    if not cover_url:
        return "-"
    return f"[Open image]({cover_url})"


def browse_templates(category: str = None, count: int = 5) -> str:
    """Return templates as a Feishu-friendly Markdown table."""
    templates = _fetch_templates(category=category, count=count)
    if templates and templates[0].get("error"):
        return f"**Error**: {templates[0]['error']}"

    if not templates:
        return "No matching templates found. Try a different category or browse all."

    lines = [
        f"## Available Product Templates ({len(templates)} results)",
        "",
        "| Image | Product | Price | Template ID | Info | Preview |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for template in templates:
        tid = template.get("templateId", "?")
        name = _escape_table_cell(template.get("name", "Unnamed Product"))
        cover = _normalize_plain_text(template.get("coverImage"))
        price_display = _extract_price(template.get("skuConfigs")) or "-"
        price_display = price_display.replace("|", "\\|")
        sku_type = _normalize_plain_text(template.get("skuType")) or "-"
        shipping = _normalize_plain_text(template.get("shippingOrigin")) or "CN"
        description = _compact_description(template.get("description", ""))
        info_parts = [f"SKU: {sku_type}", f"Ships: {shipping}"]
        if description:
            info_parts.append(description)
        info = _escape_table_cell(" · ".join(info_parts))
        image_cell = _format_image_cell(name, cover)
        preview_link = _format_preview_link(cover)

        lines.append(
            f"| {image_cell} | **{name}** | {price_display} | `{tid}` | {info} | {preview_link} |"
        )

    lines.extend(
        [
            "",
            "Use `generate_preview` with a `Template ID` to create a customized design.",
            "If a thumbnail does not render in Feishu, use the `Preview` link in the same row.",
        ]
    )
    return "\n".join(lines)


def browse_templates_json(category: str = None, count: int = 5) -> list:
    """Return JSON-serializable template data with optional local image cache."""
    templates = _fetch_templates(category=category, count=count)
    if templates and templates[0].get("error"):
        return templates

    results = []
    for i, template in enumerate(templates, 1):
        tid = template.get("templateId", "?")
        cover = _normalize_plain_text(template.get("coverImage"))
        local_cover = _download_cover_image(cover, tid)
        results.append(
            {
                "index": i,
                "templateId": tid,
                "name": template.get("name", "Unnamed Product"),
                "description": template.get("description", ""),
                "skuType": template.get("skuType", ""),
                "shippingOrigin": template.get("shippingOrigin", "CN"),
                "price": _extract_price(template.get("skuConfigs")),
                "remoteImageUrl": cover,
                "localImagePath": local_cover,
            }
        )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown table")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(browse_templates_json(category=args.category, count=args.count), ensure_ascii=False, indent=2))
    else:
        print(browse_templates(category=args.category, count=args.count))
