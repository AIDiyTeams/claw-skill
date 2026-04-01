---
name: custom-gift-leewow
version: 1.0.18
description: >-
  Browse and create custom gifts — personalized bags, mugs, phone cases,
  apparel and more. Upload any image to generate an AI-powered product mockup.
  Tools: browse_templates (NDJSON stream of per-product Feishu display payloads),
  generate_preview, get_generation_status. Display is delegated to the
  `feishu-card-display` skill. Requires CLAW_SK.
  If ClawHub is rate-limited,
  install from GitHub:
  https://github.com/AIDiyTeams/claw-skill/tree/main/custom-gift-leewow
homepage: https://github.com/AIDiyTeams/claw-skill/tree/main/custom-gift-leewow
---

# Custom Gift — Leewow

> ClawHub rate-limited? Install directly from GitHub:
> `https://github.com/AIDiyTeams/claw-skill/tree/main/custom-gift-leewow`

## Install Fallback

If ClawHub is rate-limited, install this skill directly from GitHub:

- Repository: `https://github.com/AIDiyTeams/claw-skill`
- Skill path: `custom-gift-leewow`

Manual fallback:

```bash
cd /path/to/your/openclaw-workspace
mkdir -p skills
git clone https://github.com/AIDiyTeams/claw-skill.git /tmp/claw-skill
cp -R /tmp/claw-skill/custom-gift-leewow ./skills/custom-gift-leewow
```

Create personalized gifts and custom products powered by AI. This skill provides:

| Tool | Purpose |
|------|---------|
| `browse_templates` | Discover customizable product templates (bags, accessories, home decor, apparel, etc.) |
| `generate_preview` | Upload a design image and trigger AI generation |
| `get_generation_status` | Check generation status and download preview image |

## When to Use

- User wants to **send a gift** or **create something personalized**
- User says "browse products", "show me what I can customize", "gift ideas"
- User provides an **image** and wants to turn it into a product
- User says "make this into a mug/bag/shirt", "customize this design"

## What the agent does (keep it minimal)

**Browse** — `browse_templates` prints **NDJSON** (one JSON object per stdout line). For each line with `"type":"browse_product"`, immediately follow the `feishu-card-display` skill and execute that line’s `messageToolCalls` with the `message` tool. Do not buffer until the script exits. When you see `"type":"browse_complete"`, reply **`NO_REPLY`**. On `"type":"browse_error"`, tell the user the error. This ordering lets product entries appear as each item is ready instead of waiting for the whole list.

**Preview** — `get_generation_status` also returns `displaySkill: "feishu-card-display"` plus `messageToolCalls`. Follow the `feishu-card-display` skill and execute those calls exactly, in order, then reply with **`NO_REPLY`**.

## Prerequisites

- `CLAW_SK` — Leewow Secret Key (format: `sk-leewow-{keyId}-{secret}`)
- `CLAW_BASE_URL` — API base URL (default: `https://leewow.com`)
- `CLAW_PATH_PREFIX` — Path prefix (default: `/v2` for leewow.com)
- `LEEWOW_API_BASE` — Base URL for COS STS credentials (default: `https://leewow.com`)
- Optional (recommended for Feishu browse covers): `FEISHU_APP_ID`, `FEISHU_APP_SECRET` — same app as your Feishu bot; without them, browse still works but cover thumbnails in Feishu may not display well
- Python 3.10+ with `requests` and `cos-python-sdk-v5`

## Configuration

Environment variables are loaded from `~/.openclaw/.env`:

```bash
CLAW_SK=sk-leewow-xxxx-xxxx
CLAW_BASE_URL=https://leewow.com
CLAW_PATH_PREFIX=/v2
LEEWOW_API_BASE=https://leewow.com
# Optional, for better Feishu browse rendering:
# FEISHU_APP_ID=cli_xxx
# FEISHU_APP_SECRET=xxx
```

## Image Requirements (IMPORTANT)

### For Input Images (User Upload)
- **Must be in workspace directory**: `~/.openclaw/workspace/`
- Supported formats: JPG, PNG, WebP
- Recommended: Clear, well-lit images for best results

### For Preview Images (Generated Output)
- Automatically saved to: `~/.openclaw/workspace/previews/`
- Filename format: `leewow_preview_{taskId}.{ext}`
- The agent can directly display these images to users

### COS Presigned URLs
For private COS buckets, you may need to generate **presigned URLs** for accessing images:

```bash
# Generate presigned URL for a COS image
python3 scripts/cos_presign.py "https://bucket.cos.region.myqcloud.com/key.png" --json

# With custom expiration (e.g., 1 hour = 3600 seconds)
python3 scripts/cos_presign.py "COS_URL" --expired 3600

# Use with get_generation_status to get presigned preview URL
python3 scripts/get_status.py {taskId} --presign --json
```

**Note**: Most Leewow COS buckets are public, so presigned URLs are optional.

## Typical Flow (Generator Pattern)

1. **Browse** — `browse_templates` → consume NDJSON lines; for each `browse_product`, use `feishu-card-display` rules to execute `messageToolCalls` immediately → `browse_complete` → reply `NO_REPLY` → user picks a `Template ID` when ready
2. **Upload** — User provides an image (must be in workspace `~/.openclaw/workspace/`)
3. **Generate** — Call `generate_preview` → get taskId → immediately proceed to step 4
4. **Poll** — Call `get_generation_status` with `poll=true` → wait for COMPLETED
5. **Display** — use `feishu-card-display` rules to execute returned `messageToolCalls` in order → final assistant reply is `NO_REPLY`

## Tool Reference

### browse_templates

Browse available product templates.

```bash
python3 scripts/browse.py --count 5 --json --stream
```

Options:
- `--category`: Filter by category (bag, accessory, home, apparel)
- `--count`: Number of products to return (1-10, default 5)
- `--json --stream`: NDJSON stream for agents (`browse_product` lines + `browse_complete`; default tool command)
- `--json` (without `--stream`): Single JSON object; Feishu image steps run in parallel across products
- `--raw-json`: Debug mode that returns raw template data

### generate_preview

Upload image and trigger generation.

```bash
python3 scripts/generate.py --image-path ./workspace/my_design.png --template-id 3 --json
```

Options:
- `--image-path`: **Required**. Path to design image (must be in workspace)
- `--template-id`: **Required**. Product template ID from browse_templates
- `--design-theme`: Optional style description
- `--aspect-ratio`: Image ratio (3:4, 1:1, 4:3, default 3:4)
- `--json`: Output JSON format

**Returns**: Task ID for status polling. Generation is async (~30-60s).

### get_generation_status

Check generation status and download preview image.

```bash
python3 scripts/get_status.py {taskId} --poll
```

Options:
- `task_id`: Task ID from generate_preview
- `--poll`: Wait until generation completes
- `--timeout`: Poll timeout in seconds (default 120)
- `--no-download`: Skip downloading preview image
- `--json`: Output JSON format

**Returns**: Generation status and local image path (if completed).
The agent should use `replyMarkdown` as the final text reply content.

## Safety Rules

- Never expose or log the `CLAW_SK` value. When confirming configuration, only show the last 4 characters.
- Input images **must** be in workspace directory for the agent to access them
- Preview images are automatically saved to `workspace/previews/`
- Limit browse results to 10 templates maximum per request

## Examples

```text
User: "I want to make a custom gift for my friend"
→ browse_templates → each NDJSON `browse_product` line → follow `feishu-card-display` → `browse_complete` → `NO_REPLY`
→ user picks → generate_preview → get_generation_status --poll
→ use `message` tool to send preview image as media + `replyMarkdown` → return `NO_REPLY`

User: "Turn this photo into a phone case"
→ browse_templates --category phone → NDJSON product lines as above via `feishu-card-display` → user picks
→ generate_preview → get_generation_status --poll
→ use `message` tool to send preview image as media + `replyMarkdown` → return `NO_REPLY`

User: "Show me what products I can customize"
→ browse_templates → execute each NDJSON `browse_product` line via `feishu-card-display`, then `NO_REPLY` on `browse_complete`
```

## Output Structure

### browse_templates (stdout: multiple lines)

Line 1..N (`browse_product` — emit as soon as that product is ready):

```json
{"type":"browse_product","chunkIndex":1,"chunkTotal":8,"channel":"feishu","displaySkill":"feishu-card-display","messageToolCalls":[{"action":"send","channel":"feishu","card":{"schema":"2.0","body":{"elements":[...]}}}]}
```

Final line (`browse_complete`):

```json
{"type":"browse_complete","messageCount":8,"feishuImagesResolved":true,"finalAssistantReply":"NO_REPLY","format":"browse_ndjson"}
```

→ Execute each `browse_product` line’s `messageToolCalls` with the `feishu-card-display` rules as soon as that line appears; after `browse_complete`, return `NO_REPLY`.

Optional one-shot (no `--stream` on CLI): legacy single JSON with `messageToolCalls` / `messagesMarkdown` for debugging only.

### generate_preview --json
```json
{
  "taskId": "task_xxx",
  "status": "PENDING",
  "estimatedSeconds": 45,
  "templateId": 3
}
```

### get_generation_status --json (completed)
```json
{
  "taskId": "task_xxx",
  "status": "COMPLETED",
  "purchaseUrl": "https://leewow.com/claw/preview/gen_xxx?skid=...&sig=...",
  "localImagePath": "/Users/.../.openclaw/workspace/previews/leewow_preview_task_xxx.jpg",
  "replyMarkdown": "你的定制效果图出来啦 🎉\\n\\n🛒 点击下单购买: https://...",
  "deliveryMode": "message_tool_media_then_text",
  "messageToolCalls": [
    {
      "action": "send",
      "channel": "feishu",
      "filePath": "/Users/.../.openclaw/workspace/previews/leewow_preview_task_xxx.jpg",
      "message": ""
    },
    {
      "action": "send",
      "channel": "feishu",
      "message": "你的定制效果图出来啦 🎉\\n\\n🛒 点击下单购买: https://..."
    }
  ],
  "finalAssistantReply": "NO_REPLY"
}
```
→ Agent executes `messageToolCalls` exactly, then returns `NO_REPLY`.

Version Marker: custom-gift-leewow@1.0.18
