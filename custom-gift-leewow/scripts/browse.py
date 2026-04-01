#!/usr/bin/env python3
from __future__ import annotations
"""Browse Leewow customizable product templates and send Feishu cards directly."""

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
from channel_renderers import normalize_browse_item
from claw_auth import claw_get
from feishu_direct import FeishuDirectClient, resolve_feishu_delivery_config

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


def _build_customer_message_markdown(item: dict, include_preview_link: bool = False) -> str:
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


def _prepare_feishu_cards_parallel(
    rows: list[dict],
    client: FeishuDirectClient,
) -> tuple[list[dict], bool]:
    """Build per-product Feishu card payloads in parallel while preserving order."""
    if not rows:
        return [], False
    workers = min(8, len(rows))
    results: list[dict | None] = [None] * len(rows)
    any_changed = False

    def task(idx: int, item: dict) -> tuple[int, dict]:
        markdown = _build_customer_message_markdown(item)
        try:
            card, image_resolved = client.build_card(
                markdown_text=markdown,
                image_ref=item.get("coverImage") or None,
                alt_text=item["name"],
            )
        except Exception:
            card, image_resolved = client.build_card(
                markdown_text=_build_customer_message_markdown(item, include_preview_link=True),
                image_ref=None,
                alt_text=item["name"],
            )
        return idx, {
            "card": card,
            "feishuImageResolved": image_resolved,
        }

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(task, i, item) for i, item in enumerate(rows)]
        for fut in futures:
            idx, result = fut.result()
            results[idx] = result
            if result.get("feishuImageResolved"):
                any_changed = True

    return [r for r in results if r is not None], any_changed

def browse_templates_payload(category: str = None, count: int = 5, channel: str = "feishu", params: dict | None = None) -> dict:
    """Direct-send browse cards on Feishu and return send results."""
    rows = _build_browse_items(category=category, count=count)
    if rows and rows[0].get("error"):
        return {"error": rows[0]["error"]}

    ch = (channel or "").strip().lower()
    if ch != "feishu":
        return {"error": f"Unsupported direct-send channel: {channel}"}

    try:
        app_id, app_secret, receive_id, receive_id_type, domain = resolve_feishu_delivery_config(params)
    except Exception as exc:
        return {"error": str(exc)}

    client = FeishuDirectClient(
        app_id=app_id,
        app_secret=app_secret,
        receive_id=receive_id,
        receive_id_type=receive_id_type,
        domain=domain,
    )

    plans, feishu_images_resolved = _prepare_feishu_cards_parallel(rows, client)
    message_ids: list[str] = []
    for plan in plans:
        message_ids.append(client.send_card(plan["card"]))

    return {
        "ok": True,
        "channel": channel,
        "mode": "direct_feishu_send",
        "messageCount": len(message_ids),
        "messageIds": message_ids,
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
    parser.add_argument("--json", action="store_true", help="Direct-send and output JSON result")
    parser.add_argument("--raw-json", action="store_true", help="Output raw template JSON for debugging")
    parser.add_argument("--feishu-target", type=str, default=None)
    parser.add_argument("--feishu-receive-id-type", type=str, default=None)
    parser.add_argument("--feishu-app-id", type=str, default=None)
    parser.add_argument("--feishu-app-secret", type=str, default=None)
    parser.add_argument("--feishu-open-base", type=str, default=None)
    args = parser.parse_args()

    if args.raw_json:
        print(json.dumps(browse_templates_json(category=args.category, count=args.count), ensure_ascii=False, indent=2))
    elif args.json:
        print(
            json.dumps(
                browse_templates_payload(
                    category=args.category,
                    count=args.count,
                    channel=args.channel,
                    params={
                        "feishu_target": args.feishu_target,
                        "feishu_receive_id_type": args.feishu_receive_id_type,
                        "feishu_app_id": args.feishu_app_id,
                        "feishu_app_secret": args.feishu_app_secret,
                        "feishu_open_base": args.feishu_open_base,
                    },
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                browse_templates_payload(
                    category=args.category,
                    count=args.count,
                    channel=args.channel,
                    params={
                        "feishu_target": args.feishu_target,
                        "feishu_receive_id_type": args.feishu_receive_id_type,
                        "feishu_app_id": args.feishu_app_id,
                        "feishu_app_secret": args.feishu_app_secret,
                        "feishu_open_base": args.feishu_open_base,
                    },
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
