#!/usr/bin/env python3
from __future__ import annotations
"""Browse Leewow customizable product templates.

Plain stdout: channel-specific markdown (default `feishu`: one block per product).
`--json --stream`: NDJSON — one `browse_product` line per item as soon as that
item's Feishu image handling finishes (flush per line); then `browse_complete`.
`--json` without `--stream`: one JSON object (Feishu uploads run in parallel
across products to shorten total wait).
"""

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
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
from channel_renderers import get_channel_renderer, normalize_browse_item, normalize_plain_text
from claw_auth import claw_get
from feishu_markdown_resolve import (
    FeishuMarkdownImageResolver,
    fallback_markdown_images_to_links,
    feishu_resolve_credentials_ready,
)

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


def _build_browse_items(category: str = None, count: int = 5) -> list[dict]:
    templates = _fetch_templates(category=category, count=count)
    if templates and templates[0].get("error"):
        return templates

    rows = []
    for template in templates:
        rows.append(normalize_browse_item(template, _extract_price(template.get("skuConfigs"))))
    return rows


def _process_one_feishu_markdown(
    resolver: FeishuMarkdownImageResolver, msg: str
) -> tuple[str, bool]:
    out, changed = resolver.resolve(msg)
    if not changed:
        out = fallback_markdown_images_to_links(out)
    return out, changed


def _build_customer_message_markdown(item: dict, include_preview_link: bool = True) -> str:
    price_display = str(item["price"]).replace("|", "\\|")
    lines = [
        f"## {item['name']}",
        item["description"],
        f"**Template ID:** `{item['templateId']}`",
        f"**Price:** {price_display}",
    ]
    if include_preview_link and item.get("coverImage"):
        lines.extend(["", f"[Preview: {item['name']}]({item['coverImage']})"])
    return "\n".join(lines)


def _build_feishu_product_card(item: dict, image_key: str | None) -> dict:
    body_elements: list[dict] = [
        {
            "tag": "markdown",
            "content": _build_customer_message_markdown(
                item,
                include_preview_link=image_key is None and bool(item.get("coverImage")),
            ),
        }
    ]
    if image_key:
        body_elements.append(
            {
                "tag": "img",
                "img_key": image_key,
                "alt": {
                    "tag": "plain_text",
                    "content": item["name"],
                },
            }
        )
    return {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
        },
        "body": {
            "elements": body_elements,
        },
    }


def _build_browse_message_plan(item: dict, channel: str, resolver: FeishuMarkdownImageResolver | None) -> dict:
    markdown = _build_customer_message_markdown(item, include_preview_link=bool(item.get("coverImage")))
    if (channel or "").strip().lower() != "feishu":
        return {
            "messageMarkdown": markdown,
            "messageToolCall": {
                "action": "send",
                "channel": channel,
                "message": markdown,
            },
            "feishuImageResolved": False,
        }

    image_key = resolver.resolve_image_ref(item["coverImage"]) if resolver and item.get("coverImage") else None
    card = _build_feishu_product_card(item, image_key)
    return {
        "messageMarkdown": markdown,
        "messageToolCall": {
            "action": "send",
            "channel": channel,
            "card": card,
        },
        "feishuImageResolved": bool(image_key),
    }


def _resolve_feishu_messages_parallel(
    messages: list[str],
    resolver: FeishuMarkdownImageResolver,
) -> tuple[list[str], bool]:
    """Resolve each markdown block in parallel (separate products → separate uploads)."""
    if not messages:
        return [], False
    n = len(messages)
    workers = min(8, n)
    results: list[str | None] = [None] * n
    any_changed = False

    def task(idx: int, msg: str) -> tuple[int, str, bool]:
        out, ch = _process_one_feishu_markdown(resolver, msg)
        return idx, out, ch

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(task, i, m) for i, m in enumerate(messages)]
        for fut in futures:
            idx, out, ch = fut.result()
            results[idx] = out
            if ch:
                any_changed = True
    return [r for r in results if r is not None], any_changed


def _resolve_browse_plans_parallel(
    rows: list[dict],
    channel: str,
    resolver: FeishuMarkdownImageResolver | None,
) -> tuple[list[dict], bool]:
    """Build per-product delivery plans in parallel while preserving order."""
    if not rows:
        return [], False
    workers = min(8, len(rows))
    results: list[dict | None] = [None] * len(rows)
    any_changed = False

    def task(idx: int, item: dict) -> tuple[int, dict]:
        return idx, _build_browse_message_plan(item, channel, resolver)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(task, i, item) for i, item in enumerate(rows)]
        for fut in futures:
            idx, result = fut.result()
            results[idx] = result
            if result.get("feishuImageResolved"):
                any_changed = True

    return [r for r in results if r is not None], any_changed


def _message_tool_calls(messages: list[str], channel: str) -> list[dict]:
    return [
        {"action": "send", "channel": channel, "message": message}
        for message in messages
    ]


def emit_browse_ndjson_stream(
    category: str | None = None,
    count: int = 5,
    channel: str = "feishu",
) -> None:
    """Print one JSON object per product as soon as that product is ready (line-buffered)."""
    rows = _build_browse_items(category=category, count=count)
    if rows and rows[0].get("error"):
        line = json.dumps({"type": "browse_error", "error": rows[0]["error"]}, ensure_ascii=False)
        print(line, flush=True)
        return

    renderer = get_channel_renderer(channel)
    ch = (channel or "").strip().lower()
    resolver: FeishuMarkdownImageResolver | None = None
    if ch == "feishu" and feishu_resolve_credentials_ready():
        resolver = FeishuMarkdownImageResolver()

    plans, feishu_any = _resolve_browse_plans_parallel(rows, channel, resolver)
    total = len(plans)
    for i, plan in enumerate(plans):
        chunk = {
            "type": "browse_product",
            "chunkIndex": i + 1,
            "chunkTotal": total,
            "channel": channel,
            "messageToolCalls": [plan["messageToolCall"]],
            "messagesMarkdown": [plan["messageMarkdown"]],
            "feishuImagesResolved": plan["feishuImageResolved"],
        }
        print(json.dumps(chunk, ensure_ascii=False), flush=True)

    print(
        json.dumps(
            {
                "type": "browse_complete",
                "messageCount": total,
                "feishuImagesResolved": feishu_any,
                "finalAssistantReply": "NO_REPLY",
                "format": "browse_ndjson",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def browse_templates(category: str = None, count: int = 5, channel: str = "feishu") -> str:
    """Return templates rendered for the requested channel."""
    rows = _build_browse_items(category=category, count=count)
    if rows and rows[0].get("error"):
        return f"**Error**: {rows[0]['error']}"
    renderer = get_channel_renderer(channel)
    return renderer.render_browse(rows)


def browse_templates_payload(category: str = None, count: int = 5, channel: str = "feishu") -> dict:
    """Return JSON payload for agent delivery.

    Agent sends each `messagesMarkdown` entry in order, verbatim (separate messages).
    """
    rows = _build_browse_items(category=category, count=count)
    if rows and rows[0].get("error"):
        return {"error": rows[0]["error"]}

    ch = (channel or "").strip().lower()
    resolver: FeishuMarkdownImageResolver | None = None
    if ch == "feishu" and feishu_resolve_credentials_ready():
        resolver = FeishuMarkdownImageResolver()

    plans, feishu_images_resolved = _resolve_browse_plans_parallel(rows, channel, resolver)
    messages = [plan["messageMarkdown"] for plan in plans]
    message_tool_calls = [plan["messageToolCall"] for plan in plans]

    return {
        "channel": channel,
        "format": "multi_message_card" if ch == "feishu" else "multi_message_markdown",
        "deliveryMode": "message_tool_sequential",
        "messageCount": len(messages),
        "messagesMarkdown": messages,
        "messageToolCalls": message_tool_calls,
        "feishuImagesResolved": feishu_images_resolved,
        "finalAssistantReply": "NO_REPLY",
    }


def browse_templates_json(category: str = None, count: int = 5) -> list:
    """Return raw JSON-serializable template data with optional local image cache."""
    templates = _fetch_templates(category=category, count=count)
    if templates and templates[0].get("error"):
        return templates

    results = []
    for i, template in enumerate(templates, 1):
        tid = template.get("templateId", "?")
        cover = normalize_plain_text(template.get("coverImage"))
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
    parser.add_argument("--channel", type=str, default="feishu", help="Reserved output channel renderer")
    parser.add_argument("--json", action="store_true", help="Output agent delivery JSON instead of markdown")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="With --json: NDJSON stream (one browse_product line per item as ready, then browse_complete)",
    )
    parser.add_argument("--raw-json", action="store_true", help="Output raw template JSON for debugging")
    args = parser.parse_args()

    if args.raw_json:
        print(json.dumps(browse_templates_json(category=args.category, count=args.count), ensure_ascii=False, indent=2))
    elif args.json and args.stream:
        emit_browse_ndjson_stream(category=args.category, count=args.count, channel=args.channel)
    elif args.json:
        print(json.dumps(browse_templates_payload(category=args.category, count=args.count, channel=args.channel), ensure_ascii=False, indent=2))
    else:
        print(browse_templates(category=args.category, count=args.count, channel=args.channel))
