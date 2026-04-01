#!/usr/bin/env python3
from __future__ import annotations
"""Query generation task status and output structured JSON for agent sending.

API response structure (GET /claw/task/{taskId}):
{
  "code": 0,
  "data": {
    "taskId": "gen_xxx",
    "status": "COMPLETED",              // PENDING | ANALYZING | GENERATING | CREATING_PRODUCT | COMPLETED | FAILED
    "result": {                          // only when COMPLETED
      "renderedImageUrl": "https://...myqcloud.com/...",
      "templateId": 15,
      "customizedProductId": null        // may be null if product creation is pending
    },
    "errorMessage": "...",               // only when FAILED
    "retryCount": 0                      // only when FAILED
  }
}

The task API does NOT return a previewUrl.
Preview URL format: {CLAW_PREVIEW_BASE_URL}/{taskId}  (configured via claw.preview-base-url on the Java side).
Python signs this URL with skid/sig so the preview page can exchange for a JWT.
"""

import argparse
import json
import os
import sys
import time

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

from claw_auth import claw_get, sign_url
import requests

CLAW_BASE_URL = os.getenv("CLAW_BASE_URL", "https://leewow.com")
CLAW_PATH_PREFIX = os.getenv("CLAW_PATH_PREFIX", "")
CLAW_SK = os.getenv("CLAW_SK", "")
CLAW_PREVIEW_BASE_URL = os.getenv("CLAW_PREVIEW_BASE_URL", f"{CLAW_BASE_URL}/claw/preview")

WORKSPACE_DIR = os.path.expanduser("~/.openclaw/workspace")


def get_task_status(task_id: str, download_image: bool = True) -> dict:
    """Query task status, download preview image, build signed purchase URL."""
    if not CLAW_SK:
        return {"error": "CLAW_SK environment variable is not set."}

    url = f"{CLAW_BASE_URL}{CLAW_PATH_PREFIX}/claw/task/{task_id}"

    try:
        resp = claw_get(CLAW_SK, url, timeout=15)
        data = resp.json()
    except Exception as e:
        return {"error": f"Failed to fetch task status: {e}"}

    if data.get("code") != 0:
        return {"error": f"API returned: {data.get('message', 'Unknown error')}"}

    raw = data.get("data", {})
    status = raw.get("status", "UNKNOWN")
    result_nested = raw.get("result", {}) or {}

    out = {
        "taskId": raw.get("taskId", task_id),
        "status": status,
        "templateId": result_nested.get("templateId"),
    }

    if status == "COMPLETED":
        rendered_url = result_nested.get("renderedImageUrl")

        if download_image and rendered_url:
            local_path = _download_preview(rendered_url, task_id)
            if local_path:
                out["localImagePath"] = local_path

        preview_url = f"{CLAW_PREVIEW_BASE_URL}/{task_id}"
        out["purchaseUrl"] = sign_url(CLAW_SK, preview_url)
        out["replyMarkdown"] = _build_completed_reply_markdown(
            task_id=out["taskId"],
            template_id=out.get("templateId"),
            purchase_url=out["purchaseUrl"],
        )
        out["deliveryMode"] = "message_tool_media_then_text"
        out["finalAssistantReply"] = "NO_REPLY"

    elif status == "FAILED":
        out["errorMessage"] = raw.get("errorMessage", "Unknown error")
        out["replyMarkdown"] = _build_failed_reply_markdown(
            task_id=out["taskId"],
            error_message=out["errorMessage"],
        )
        out["deliveryMode"] = "message_tool_text_only"
        out["finalAssistantReply"] = "NO_REPLY"
    else:
        out["replyMarkdown"] = _build_pending_reply_markdown(
            task_id=out["taskId"],
            template_id=out.get("templateId"),
            status=status,
        )
        out["deliveryMode"] = "message_tool_text_only"
        out["finalAssistantReply"] = "NO_REPLY"

    return out


def _download_preview(image_url: str, task_id: str) -> str | None:
    """Download preview image to workspace/previews/."""
    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()

        ext = ".png"
        ct = resp.headers.get("content-type", "")
        if "jpeg" in ct or "jpg" in ct:
            ext = ".jpg"
        elif "webp" in ct:
            ext = ".webp"

        previews_dir = os.path.join(WORKSPACE_DIR, "previews")
        os.makedirs(previews_dir, exist_ok=True)

        filepath = os.path.join(previews_dir, f"leewow_preview_{task_id}{ext}")
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath
    except Exception as e:
        print(f"Warning: Failed to download preview image: {e}", file=sys.stderr)
        return None


def poll_until_complete(task_id: str, timeout: int = 120, download_image: bool = True) -> dict:
    """Poll task status until COMPLETED / FAILED / timeout."""
    start = time.time()

    while time.time() - start < timeout:
        result = get_task_status(task_id, download_image=False)

        if "error" in result:
            return result

        status = result.get("status", "UNKNOWN")
        if status == "COMPLETED":
            return get_task_status(task_id, download_image=download_image)
        if status == "FAILED":
            return result

        time.sleep(5)

    return {"error": f"Timeout after {timeout}s", "taskId": task_id, "status": "TIMEOUT"}


def _build_completed_reply_markdown(task_id: str, template_id, purchase_url: str) -> str:
    lines = [
        "你的定制效果图出来啦 🎉",
        f"🛒 点击下单购买: {purchase_url}",
        f"📦 模板ID: {template_id or '?'} | 任务ID: {task_id}",
        "",
        "喜欢吗？如果想调整或者试试其他产品，告诉我！",
    ]
    return "\n".join(lines)


def _build_failed_reply_markdown(task_id: str, error_message: str) -> str:
    return (
        f"## 生成失败 ❌\n\n"
        f"**任务ID**: `{task_id}`\n"
        f"**原因**: {error_message}\n\n"
        f"可以换张图片或者换个模板再试一次。"
    )


def _build_pending_reply_markdown(task_id: str, template_id, status: str) -> str:
    return (
        f"## 正在生成中 ⏳\n\n"
        f"**任务ID**: `{task_id}` | **模板**: #{template_id or '?'}\n"
        f"**状态**: {status}\n\n"
        f"请稍等，正在努力生成效果图..."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Leewow generation task status")
    parser.add_argument("task_id", help="Task ID from generate_preview")
    parser.add_argument("--poll", action="store_true", help="Poll until complete")
    parser.add_argument("--timeout", type=int, default=120, help="Poll timeout in seconds")
    parser.add_argument("--no-download", action="store_true", help="Skip downloading preview image")
    parser.add_argument("--json", action="store_true", help="(compat) output JSON")
    args = parser.parse_args()

    if args.poll:
        result = poll_until_complete(args.task_id, args.timeout, download_image=not args.no_download)
    else:
        result = get_task_status(args.task_id, download_image=not args.no_download)

    print(json.dumps(result, ensure_ascii=False, indent=2))
