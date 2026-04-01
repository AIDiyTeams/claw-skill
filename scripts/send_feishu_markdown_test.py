#!/usr/bin/env python3
from __future__ import annotations

"""Test-only Feishu probe sender.

This script is for manual rendering validation only. It is not part of the
custom-gift-leewow production skill tool path.
"""

from send_channel_render_probe import main


if __name__ == "__main__":
    raise SystemExit(main(default_channel="feishu"))
