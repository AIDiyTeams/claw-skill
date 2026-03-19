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


def _generate_presigned_url_if_needed(image_url: str, expired: int = 3600) -> str:
    """Generate presigned URL for COS objects if necessary.
    
    For public COS buckets, the original URL works fine.
    For private buckets, this generates a temporary signed URL.
    """
    try:
        # Try to access the original URL first
        resp = requests.head(image_url, timeout=5, allow_redirects=True)
        if resp.status_code == 200:
            # URL is accessible, no need for presigned URL
            return image_url
    except:
        pass
    
    # Try to generate presigned URL
    try:
        from cos_presign import generate_presigned_url
        return generate_presigned_url(image_url, expired)
    except Exception:
        # If presign fails, return original URL
        return image_url


def get_task_status(task_id: str, download_image: bool = True, presign: bool = False) -> dict:
    """Query task status and optionally download preview image.
    
    Args:
        task_id: The generation task ID
        download_image: Whether to download the preview image locally
        presign: Whether to generate presigned URL for COS images
    """
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
    
    # Generate presigned URL if requested and task is completed
    if presign and status == "COMPLETED":
        rendered_url = result.get("renderedImageUrl") or result.get("result", {}).get("renderedImageUrl")
        if rendered_url and "myqcloud.com" in rendered_url:
            presigned_url = _generate_presigned_url_if_needed(rendered_url)
            result["presignedImageUrl"] = presigned_url
    
    # Download preview image if task is completed
    image_path = None
    if download_image and status == "COMPLETED":
        preview_url = result.get("previewImageUrl") or result.get("resultImageUrl")
        if not preview_url:
            # Try to get from result.renderedImageUrl
            preview_url = result.get("renderedImageUrl") or result.get("result", {}).get("renderedImageUrl")
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


def poll_until_complete(task_id: str, timeout: int = 120, download_image: bool = True, presign: bool = False) -> dict:
    """Poll task status until completed or timeout."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        result = get_task_status(task_id, download_image=False, presign=False)  # Don't download/presign during polling
        
        if "error" in result:
            return result
        
        status = result.get("status", "UNKNOWN")
        
        if status == "COMPLETED":
            # Download image and generate presigned URL on completion
            return get_task_status(task_id, download_image=download_image, presign=presign)
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
    parser.add_argument("--presign", action="store_true", help="Generate presigned URL for COS images")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    args = parser.parse_args()
    
    if args.poll:
        result = poll_until_complete(args.task_id, args.timeout, download_image=not args.no_download, presign=args.presign)
    else:
        result = get_task_status(args.task_id, download_image=not args.no_download, presign=args.presign)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_result(result))
