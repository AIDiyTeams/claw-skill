---
name: custom-gift-leewow
version: 1.0.19
description: >-
  Browse and create custom gifts — personalized bags, mugs, phone cases,
  apparel and more. Upload any image to generate an AI-powered product mockup.
  Tools: browse_templates (Python direct Feishu card send), generate_preview,
  get_generation_status (Python direct Feishu result send). Requires CLAW_SK.
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

**Browse** — `browse_templates` sends Feishu product cards directly from Python and returns only send results. If the tool succeeds, reply with **`NO_REPLY`**. Do not retell the product list in normal assistant text.

**Preview** — `get_generation_status` sends the generated preview result directly to Feishu from Python and returns only send results. If the tool succeeds, reply with **`NO_REPLY`**.

## Prerequisites

- `CLAW_SK` — Leewow Secret Key (format: `sk-leewow-{keyId}-{secret}`)
- Obtain it from: `https://leewow.com/profile/secret-keys`
- `FEISHU_APP_ID` — Feishu App ID (often referred to together with App Secret as app AK/SK)
- `FEISHU_APP_SECRET` — Feishu App Secret
- Obtain them from your Feishu Open Platform app settings page
- `FEISHU_RECEIVE_ID` — default Feishu target for this skill to send into
- `FEISHU_RECEIVE_ID_TYPE` — optional, defaults to `chat_id`
- `CLAW_BASE_URL` — API base URL (default: `https://leewow.com`)
- `CLAW_PATH_PREFIX` — Path prefix (default: `/v2` for leewow.com)
- `LEEWOW_API_BASE` — Base URL for COS STS credentials (default: `https://leewow.com`)
- Python 3.10+ with `requests` and `cos-python-sdk-v5`

## Configuration

Environment variables are loaded from `~/.openclaw/.env`:

```bash
CLAW_SK=sk-leewow-xxxx-xxxx
# Feishu App ID / App Secret (app AK/SK)
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
# Default target for direct Feishu send
FEISHU_RECEIVE_ID=oc_xxx_or_open_id
FEISHU_RECEIVE_ID_TYPE=chat_id
CLAW_BASE_URL=https://leewow.com
CLAW_PATH_PREFIX=/v2
LEEWOW_API_BASE=https://leewow.com
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

1. **Browse** — `browse_templates` → Python sends Feishu product cards directly → agent replies `NO_REPLY` → user picks a `Template ID` when ready
2. **Upload** — User provides an image (must be in workspace `~/.openclaw/workspace/`)
3. **Generate** — Call `generate_preview` → get taskId → immediately proceed to step 4
4. **Poll** — Call `get_generation_status` with `poll=true` → wait for COMPLETED
5. **Display** — `get_generation_status` → Python sends preview result directly → final assistant reply is `NO_REPLY`

## Tool Reference

### browse_templates

Browse available product templates.

```bash
python3 scripts/browse.py --count 5 --json
```

Options:
- `--category`: Filter by category (bag, accessory, home, apparel)
- `--count`: Number of products to return (1-10, default 5)
- `--json`: Direct-send to Feishu and return send result JSON
- `--feishu-target`: Optional target override
- `--feishu-receive-id-type`: Optional target type override
- `--feishu-app-id`: Optional app id override
- `--feishu-app-secret`: Optional app secret override
- `--feishu-open-base`: Optional Open API base override
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

**Returns**: Generation status and, in direct-send mode, send result JSON.

## Safety Rules

- Never expose or log the `CLAW_SK` value. When confirming configuration, only show the last 4 characters.
- Input images **must** be in workspace directory for the agent to access them
- Preview images are automatically saved to `workspace/previews/`
- Limit browse results to 10 templates maximum per request

## Examples

```text
User: "I want to make a custom gift for my friend"
→ browse_templates → Python sends product cards directly → `NO_REPLY`
→ user picks → generate_preview → get_generation_status --poll
→ Python sends preview image + text directly → `NO_REPLY`

User: "Turn this photo into a phone case"
→ browse_templates --category phone → Python sends product cards directly → user picks
→ generate_preview → get_generation_status --poll
→ Python sends preview image + text directly → `NO_REPLY`

User: "Show me what products I can customize"
→ browse_templates → Python sends product cards directly → `NO_REPLY`
```

## Output Structure

### browse_templates --json

```json
{
  "ok": true,
  "mode": "direct_feishu_send",
  "channel": "feishu",
  "messageCount": 8,
  "messageIds": ["om_xxx", "om_yyy"],
  "feishuImagesResolved": true,
  "finalAssistantReply": "NO_REPLY"
}
```

→ Python sends product cards directly to Feishu. Agent returns `NO_REPLY`.

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
  "mode": "direct_feishu_send",
  "messageCount": 2,
  "messageIds": ["om_img_xxx", "om_text_xxx"],
  "finalAssistantReply": "NO_REPLY"
}
```
→ Python sends preview image + text directly. Agent returns `NO_REPLY`.

Version Marker: custom-gift-leewow@1.0.19
