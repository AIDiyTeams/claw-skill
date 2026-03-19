#!/usr/bin/env python3
"""Browse Leewow customizable product templates, output Markdown cards."""

import argparse
import json
import os
import sys

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

from claw_auth import claw_get

CLAW_BASE_URL = os.getenv("CLAW_BASE_URL", "https://leewow.com")
CLAW_PATH_PREFIX = os.getenv("CLAW_PATH_PREFIX", "")
CLAW_SK = os.getenv("CLAW_SK", "")


def browse_templates(category: str = None, count: int = 3) -> str:
    if not CLAW_SK:
        return "**Error**: CLAW_SK environment variable is not set."

    count = min(max(count, 1), 5)
    url = f"{CLAW_BASE_URL}{CLAW_PATH_PREFIX}/claw/templates"

    try:
        resp = claw_get(CLAW_SK, url, timeout=15)
        data = resp.json()
    except Exception as e:
        return f"**Error**: Failed to fetch templates: {e}"

    if data.get("code") != 0:
        return f"**Error**: API returned: {data.get('message', 'Unknown error')}"

    templates = data.get("data", [])

    if category:
        cat_lower = category.lower()
        templates = [
            t for t in templates
            if cat_lower in (t.get("name", "") + t.get("description", "")).lower()
        ]

    templates = templates[:count]

    if not templates:
        return "No matching templates found. Try a different category or browse all."

    lines = [f"## Available Product Templates ({len(templates)} results)\n"]

    for i, t in enumerate(templates, 1):
        tid = t.get("templateId", "?")
        name = t.get("name", "Unnamed Product")
        cover = t.get("coverImage", "")
        desc = t.get("description", "")
        sku_type = t.get("skuType", "")
        shipping = t.get("shippingOrigin", "CN")

        price_display = _extract_price(t.get("skuConfigs"))

        lines.append(f"### {i}. {name}")
        if cover:
            lines.append(f"![{name}]({cover})")
        if price_display:
            lines.append(f"Price: {price_display}")
        if desc:
            lines.append(desc)
        lines.append(f"Template ID: `{tid}` | SKU: {sku_type} | Ships from: {shipping}")
        lines.append("")

    lines.append("---")
    lines.append("*Use `gift-generate` with a Template ID to create a customized design.*")
    return "\n".join(lines)


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


def browse_templates_json(category: str = None, count: int = 3) -> list:
    """Return templates as JSON-serializable list."""
    if not CLAW_SK:
        return []

    count = min(max(count, 1), 5)
    url = f"{CLAW_BASE_URL}{CLAW_PATH_PREFIX}/claw/templates"

    try:
        resp = claw_get(CLAW_SK, url, timeout=15)
        data = resp.json()
    except Exception:
        return []

    if data.get("code") != 0:
        return []

    templates = data.get("data", [])

    if category:
        cat_lower = category.lower()
        templates = [
            t for t in templates
            if cat_lower in (t.get("name", "") + t.get("description", "")).lower()
        ]

    return templates[:count]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    
    if args.json:
        import json as json_module
        templates = browse_templates_json(category=args.category, count=args.count)
        print(json_module.dumps(templates, ensure_ascii=False))
    else:
        print(browse_templates(category=args.category, count=args.count))
