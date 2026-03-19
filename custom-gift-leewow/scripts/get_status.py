#!/usr/bin/env python3
"""Query generation task status and download preview image."""

import argparse
import json
import os
import sys
import time
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

from claw_auth import claw_get
import requests

CLAW_BASE_URL = os.getenv("CLAW_BASE_URL", "https://leewow.com")
CLAW_PATH_PREFIX = os.getenv("CLAW_PATH_PREFIX", "")
CLAW_SK = os.getenv("CLAW_SK", "")

# Workspace directory for saving preview images
WORKSPACE_DIR = os.path.expanduser("~/.openclaw/workspace")


def get_task_status(task_id: str, download_image: bool = True) -> dict:
    """Query task status and optionally download preview image."""
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

    result = data.get("data", {})
    status = result.get("status", "UNKNOWN")
    
    # Download preview image if task is completed
    image_path = None
    if download_image and status == "COMPLETED":
        preview_url = result.get("previewImageUrl") or result.get("resultImageUrl")
        if preview_url:
            image_path = download_preview_image(preview_url, task_id)
            if image_path:
                result["localImagePath"] = image_path

    return result


def download_preview_image(image_url: str, task_id: str) -> str:
    """Download preview image to workspace directory.
    
    IMPORTANT: Images must be saved to workspace directory (~/.openclaw/workspace)
    for the agent to access and return them to users.
    """
    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        
        # Determine file extension from URL or content-type
        ext = ".jpg"
        content_type = resp.headers.get("content-type", "")
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        
        # Create previews directory if not exists
        previews_dir = os.path.join(WORKSPACE_DIR, "previews")
        os.makedirs(previews_dir, exist_ok=True)
        
        # Save image with task_id as filename
        filename = f"leewow_preview_{task_id}{ext}"
        filepath = os.path.join(previews_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(resp.content)
        
        return filepath
    except Exception as e:
        print(f"Warning: Failed to download preview image: {e}", file=sys.stderr)
        return None


def poll_until_complete(task_id: str, timeout: int = 120, download_image: bool = True) -> dict:
    """Poll task status until completed or timeout."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        result = get_task_status(task_id, download_image=False)  # Don't download during polling
        
        if "error" in result:
            return result
        
        status = result.get("status", "UNKNOWN")
        
        if status == "COMPLETED":
            # Download image on completion
            if download_image:
                preview_url = result.get("previewImageUrl") or result.get("resultImageUrl")
                if preview_url:
                    image_path = download_preview_image(preview_url, task_id)
                    if image_path:
                        result["localImagePath"] = image_path
            return result
        elif status == "FAILED":
            return result
        
        # Wait before next poll
        time.sleep(5)
    
    return {"error": f"Timeout after {timeout}s", "taskId": task_id, "status": "TIMEOUT"}


def format_result(result: dict) -> str:
    """Format result as Markdown."""
    status = result.get("status", "UNKNOWN")
    task_id = result.get("taskId", "unknown")
    template_id = result.get("templateId", "?")
    
    lines = [f"## Generation Status: {status}\n"]
    lines.append(f"**Task ID**: `{task_id}`")
    lines.append(f"**Template**: #{template_id}")
    
    if status == "COMPLETED":
        lines.append("\n✅ **Generation complete!**")
        
        # Local image path
        image_path = result.get("localImagePath")
        if image_path:
            lines.append(f"\n**Preview Image**: `{image_path}`")
            lines.append(f"\n![Preview]({image_path})")
        
        # Preview URL
        preview_url = result.get("previewUrl") or result.get("resultPreviewUrl")
        if preview_url:
            lines.append(f"\n**Order Link**: [{preview_url}]({preview_url})")
    
    elif status == "FAILED":
        error_msg = result.get("errorMessage", "Unknown error")
        lines.append(f"\n❌ **Failed**: {error_msg}")
    
    elif status == "PENDING":
        lines.append("\n⏳ **Processing**... Please wait.")
    
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Leewow generation task status")
    parser.add_argument("task_id", help="Task ID from generate_preview")
    parser.add_argument("--poll", action="store_true", help="Poll until complete")
    parser.add_argument("--timeout", type=int, default=120, help="Poll timeout in seconds")
    parser.add_argument("--no-download", action="store_true", help="Skip downloading preview image")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    args = parser.parse_args()
    
    if args.poll:
        result = poll_until_complete(args.task_id, args.timeout, download_image=not args.no_download)
    else:
        result = get_task_status(args.task_id, download_image=not args.no_download)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_result(result))
