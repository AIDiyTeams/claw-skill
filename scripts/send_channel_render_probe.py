#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CUSTOM_GIFT_SCRIPTS = "/Users/apple/LeeWoW/leewow-skills/custom-gift-leewow/scripts"
if CUSTOM_GIFT_SCRIPTS not in sys.path:
    sys.path.insert(0, CUSTOM_GIFT_SCRIPTS)

from feishu_direct import FeishuDirectClient


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def parse_args(default_channel: str | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a reusable channel render probe")
    parser.add_argument("--channel", type=str, default=default_channel or "feishu", help="Target channel")
    parser.add_argument(
        "--file",
        type=str,
        default=str(Path(__file__).with_name("feishu_render_probe.md")),
        help="Markdown file to send",
    )
    parser.add_argument("--mode", type=str, default="card", help="Channel-specific render mode")
    parser.add_argument(
        "--receive-id",
        type=str,
        default=env("FEISHU_RECEIVE_ID", ""),
        help="Target receive_id. Defaults to FEISHU_RECEIVE_ID",
    )
    parser.add_argument(
        "--receive-id-type",
        type=str,
        default=env("FEISHU_RECEIVE_ID_TYPE", "chat_id"),
        help="Target receive_id type. Defaults to FEISHU_RECEIVE_ID_TYPE or chat_id",
    )
    return parser.parse_args()


def main(default_channel: str | None = None) -> int:
    args = parse_args(default_channel=default_channel)
    if not args.receive_id:
        raise SystemExit("Missing target receive_id. Pass --receive-id or set FEISHU_RECEIVE_ID.")
    if (args.channel or "").strip().lower() != "feishu":
        raise SystemExit("This probe currently supports feishu only.")

    app_id = env("FEISHU_APP_ID")
    app_secret = env("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise SystemExit("Missing FEISHU_APP_ID / FEISHU_APP_SECRET")

    client = FeishuDirectClient(
        app_id=app_id,
        app_secret=app_secret,
        receive_id=args.receive_id,
        receive_id_type=args.receive_id_type,
        domain=env("FEISHU_OPEN_BASE", "https://open.feishu.cn") or "https://open.feishu.cn",
    )

    message_id, image_resolved = client.send_markdown_card(
        markdown_text=read_text(args.file),
        image_ref=None,
        alt_text="probe",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "channel": "feishu",
                "mode": args.mode,
                "receiveIdType": args.receive_id_type,
                "messageId": message_id,
                "file": args.file,
                "imagesResolved": image_resolved,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
