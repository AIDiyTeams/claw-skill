#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Dict

import requests

from channel_messaging.base import ChannelMessenger, SendResult


DEFAULT_DOMAIN = "https://open.feishu.cn"
VALID_MODES = {"card", "post"}
VALID_RECEIVE_ID_TYPES = {"chat_id", "open_id", "user_id", "union_id", "email"}
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
CACHE_PATH = Path.home() / ".openclaw" / "cache" / "feishu_image_keys.json"


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def require_env(name: str) -> str:
    value = env(name)
    if value:
        return value
    raise SystemExit(f"Missing required env var: {name}")


class FeishuMessenger(ChannelMessenger):
    channel = "feishu"

    def __init__(self, domain: str | None = None):
        self.domain = (domain or env("FEISHU_OPEN_BASE", DEFAULT_DOMAIN) or DEFAULT_DOMAIN).rstrip("/")
        self.app_id = require_env("FEISHU_APP_ID")
        self.app_secret = require_env("FEISHU_APP_SECRET")
        self.token: str | None = None
        self.image_cache = self._load_cache()

    def send_markdown(
        self,
        markdown: str,
        receive_id: str,
        receive_id_type: str,
        mode: str,
    ) -> SendResult:
        if mode not in VALID_MODES:
            raise SystemExit(f"Invalid mode '{mode}'. Supported: {', '.join(sorted(VALID_MODES))}")
        if receive_id_type not in VALID_RECEIVE_ID_TYPES:
            raise SystemExit(
                f"Invalid receive_id_type '{receive_id_type}'. "
                f"Supported: {', '.join(sorted(VALID_RECEIVE_ID_TYPES))}"
            )

        token = self._get_token()
        resolved_markdown = self._resolve_markdown_images(markdown, token)
        payload = self._build_card_payload(resolved_markdown) if mode == "card" else self._build_post_payload(resolved_markdown)
        result = self._send_message(token, receive_id, receive_id_type, payload)
        message_id = (((result.get("data") or {}).get("message_id")) or "").strip()
        return SendResult(
            channel=self.channel,
            message_id=message_id,
            receive_id_type=receive_id_type,
            images_resolved=resolved_markdown != markdown,
        )

    def _get_token(self) -> str:
        if self.token:
            return self.token

        response = requests.post(
            f"{self.domain}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Token API failed: {json.dumps(payload, ensure_ascii=False)}")
        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError("tenant_access_token missing from Feishu response")
        self.token = token
        return token

    def _resolve_markdown_images(self, markdown: str, token: str) -> str:
        replacements: Dict[str, str] = {}

        def replace(match: re.Match[str]) -> str:
            alt = match.group(1)
            image_ref = match.group(2).strip()
            if image_ref not in replacements:
                replacements[image_ref] = self._upload_image(token, image_ref)
            return f"![{alt}]({replacements[image_ref]})"

        return MARKDOWN_IMAGE_RE.sub(replace, markdown)

    def _upload_image(self, token: str, image_ref: str) -> str:
        image_bytes, filename = self._load_image_bytes(image_ref)
        cache_key = hashlib.sha256(image_bytes).hexdigest()
        cached = self.image_cache.get(cache_key)
        if cached:
            return cached

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        response = requests.post(
            f"{self.domain}/open-apis/im/v1/images",
            headers={"Authorization": f"Bearer {token}"},
            data={"image_type": "message"},
            files={"image": (filename, image_bytes, content_type)},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Image upload failed: {json.dumps(payload, ensure_ascii=False)}")
        image_key = ((payload.get("data") or {}).get("image_key") or "").strip()
        if not image_key:
            raise RuntimeError(f"Image upload missing image_key: {json.dumps(payload, ensure_ascii=False)}")

        self.image_cache[cache_key] = image_key
        self._save_cache(self.image_cache)
        return image_key

    def _load_image_bytes(self, image_ref: str) -> tuple[bytes, str]:
        image_path = Path(image_ref)
        if image_path.is_file():
            return image_path.read_bytes(), image_path.name

        response = requests.get(image_ref, timeout=30)
        response.raise_for_status()
        filename = Path(image_ref.split("?", 1)[0]).name or "image.png"
        return response.content, filename

    def _send_message(self, token: str, receive_id: str, receive_id_type: str, payload: dict) -> dict:
        response = requests.post(
            f"{self.domain}/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"receive_id": receive_id, **payload},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Send API failed: {json.dumps(data, ensure_ascii=False)}")
        return data

    @staticmethod
    def _build_card_payload(markdown: str) -> dict:
        return {
            "msg_type": "interactive",
            "content": json.dumps(
                {
                    "schema": "2.0",
                    "config": {"wide_screen_mode": True},
                    "body": {"elements": [{"tag": "markdown", "content": markdown}]},
                },
                ensure_ascii=False,
            ),
        }

    @staticmethod
    def _build_post_payload(markdown: str) -> dict:
        return {
            "msg_type": "post",
            "content": json.dumps(
                {
                    "zh_cn": {
                        "content": [
                            [
                                {
                                    "tag": "md",
                                    "text": markdown,
                                }
                            ]
                        ]
                    }
                },
                ensure_ascii=False,
            ),
        }

    @staticmethod
    def _load_cache() -> dict[str, str]:
        if not CACHE_PATH.exists():
            return {}
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(key): str(value) for key, value in data.items()}
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    @staticmethod
    def _save_cache(data: dict[str, str]) -> None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
