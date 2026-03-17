#!/usr/bin/env python3
"""Upload image to COS, call /claw/generate, output Markdown preview card."""

import argparse
import os
import sys

from claw_auth import claw_post
from cos_uploader import upload_file_to_cos

CLAW_BASE_URL = os.getenv("CLAW_BASE_URL", "https://leewow.com")
CLAW_PATH_PREFIX = os.getenv("CLAW_PATH_PREFIX", "")
CLAW_SK = os.getenv("CLAW_SK", "")


def generate_preview(image_path: str, template_id: int,
                     design_theme: str = "", aspect_ratio: str = "3:4") -> str:
    if not CLAW_SK:
        return "**Error**: CLAW_SK environment variable is not set."

    if not os.path.exists(image_path):
        return f"**Error**: Image file not found: {image_path}"

    try:
        image_url = upload_file_to_cos(image_path, key_prefix="prod-h5-generation-upload/claw-skill")
    except Exception as e:
        return f"**Error**: Failed to upload image: {e}"

    url = f"{CLAW_BASE_URL}{CLAW_PATH_PREFIX}/claw/generate"
    payload = {
        "templateId": template_id,
        "imageUrl": image_url,
        "designTheme": design_theme,
        "aspectRatio": aspect_ratio,
    }

    try:
        resp = claw_post(CLAW_SK, url, json_data=payload, timeout=30)
        data = resp.json()
    except Exception as e:
        return f"**Error**: Failed to call generate API: {e}"

    if data.get("code") != 0:
        return f"**Error**: API returned: {data.get('message', 'Unknown error')}"

    result = data.get("data", {})
    task_id = result.get("taskId", "unknown")
    preview_url = result.get("previewUrl", "")
    status = result.get("status", "PENDING")
    estimated = result.get("estimatedSeconds", 45)

    lines = [
        "## Design Generation Started\n",
        f"**Status**: {status}",
        f"**Estimated time**: ~{estimated} seconds\n",
    ]
    if preview_url:
        lines.append(f"**Preview**: [{preview_url}]({preview_url})\n")
    lines.append(f"**Task ID**: `{task_id}`")
    lines.append(f"**Template**: #{template_id}")
    if design_theme:
        lines.append(f"**Theme**: {design_theme}")
    lines.extend([
        "",
        "---",
        "*Click the preview link to see the result once ready. You can select sizes and place an order from the preview page.*",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-path", type=str, required=True)
    parser.add_argument("--template-id", type=int, required=True)
    parser.add_argument("--design-theme", type=str, default="")
    parser.add_argument("--aspect-ratio", type=str, default="3:4")
    args = parser.parse_args()
    print(generate_preview(args.image_path, args.template_id, args.design_theme, args.aspect_ratio))
