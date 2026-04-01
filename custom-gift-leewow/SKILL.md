---
name: custom-gift-leewow
description: >-
  Browse and create custom gifts — personalized bags, mugs, phone cases,
  apparel and more. Upload any image to generate an AI-powered product mockup.
  Includes tools: browse_templates (discover products), generate_preview
  (create a design from an image), and get_generation_status (check generation
  progress). browse_templates returns a Feishu-friendly markdown table with an
  image column. Generated previews are still downloaded to workspace for
  display. Powered by Leewow. Requires CLAW_SK. If ClawHub is rate-limited,
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

## Browse Output Format

`browse_templates` now returns a **Feishu-friendly Markdown table**:
- The first column is a remote image thumbnail
- Each row includes name, price, template ID, and a preview link
- Send the table output **directly as text** so OpenClaw/Feishu can render it as an interactive card

Do **not** unpack the browse result into multiple image messages unless the user explicitly asks for separate images.

## Channel Design

This skill now follows a channel-extension design:
- Business scripts return normalized product / task data
- Python channel renderers transform that data into ready-to-send content
- The agent should treat browse output as final presentation content, not something to reformat

Current implementation:
- `feishu` renderer is implemented and tested

Reserved for future:
- Other communication channels should be added as new renderer / messenger implementations without changing the business scripts
- The agent should not guess unsupported channels or invent channel-specific formatting

## Generator Output Format (MUST FOLLOW)

This skill uses a **two-step generator pattern**.

### Step 1: Browse — Show Templates

After calling `browse_templates`, the tool returns one Markdown table string.

Expected usage:
1. Send the returned table **as-is**
2. Ask the user to choose a `Template ID`

Example:

```md
| Image | Product | Price | Template ID | Info | Preview |
| --- | --- | --- | --- | --- | --- |
| ![Canvas Tote](https://...) | **Canvas Tote Bag** | **$19.9 USD** | `12` | SKU: tote · Ships: CN | [Open image](https://...) |
```

**Rules for Step 1:**
- MUST keep the browse result in table form
- MUST preserve the `Template ID` column
- SHOULD keep the preview link column as fallback when Feishu thumbnail rendering is inconsistent
- Do NOT convert the browse result into one-message-per-image unless the user asks
- Do NOT rewrite the returned layout for the current channel unless the user explicitly asks to change the presentation

### Step 2: Generation Complete — Show Preview + Purchase Link

After `get_generation_status` returns COMPLETED, the JSON contains:
- `localImagePath` — preview image in workspace
- `purchaseUrl` — signed purchase/order page link

You MUST:
1. **Send the preview image as a media attachment** using `localImagePath`
2. **Send the purchase link** in the text message

Example:

```
[send image: /Users/.../.openclaw/workspace/previews/leewow_preview_task_xxx.jpg]

你的定制效果图出来啦 🎉
🛒 点击下单购买: https://leewow.com/claw/preview/gen_xxx?skid=...&sig=...

喜欢吗？如果想调整或者试试其他产品，告诉我！
```

**Rules for Step 2:**
- MUST send the preview image as media — this is the whole point
- MUST include the purchase link (it's pre-signed with skid/sig)
- Do NOT just describe the product in text — the user needs to SEE the image

### Common Mistakes to AVOID

❌ Breaking `browse_templates` into many standalone image messages when the intended result is a table
❌ Using `![image](local_path)` markdown for generated preview images — local paths still need media sending
❌ Just saying "完成啦！" and describing the product in text without sending the generated preview image
❌ Omitting the purchase/order link
❌ Dropping the `Template ID` column from the browse table
❌ Saying "图片已下载到本地" without actually sending the generated preview image

## Prerequisites

- `CLAW_SK` — Leewow Secret Key (format: `sk-leewow-{keyId}-{secret}`)
- `CLAW_BASE_URL` — API base URL (default: `https://leewow.com`)
- `CLAW_PATH_PREFIX` — Path prefix (default: `/v2` for leewow.com)
- `LEEWOW_API_BASE` — Base URL for COS STS credentials (default: `https://leewow.com`)
- Python 3.10+ with `requests` and `cos-python-sdk-v5`

## Configuration

Environment variables are loaded from `~/.openclaw/.env`:

```bash
CLAW_SK=sk-leewow-xxxx-xxxx
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

1. **Browse (Step 1)** — Call `browse_templates` → get a Markdown table with image column / price / template ID / preview link → send the table directly → ask user to pick
2. **Upload** — User provides an image (must be in workspace `~/.openclaw/workspace/`)
3. **Generate** — Call `generate_preview` → get taskId → immediately proceed to step 4
4. **Poll** — Call `get_generation_status` with `poll=true` → wait for COMPLETED
5. **Display (Step 2)** — **Send preview image as media** (`localImagePath`) + text with PURCHASE LINK (`purchaseUrl`)

## Tool Reference

### browse_templates

Browse available product templates.

```bash
python3 scripts/browse.py --count 5
```

Options:
- `--category`: Filter by category (bag, accessory, home, apparel)
- `--count`: Number of rows in the table (1-10, default 5)
- `--json`: Optional debug / compatibility mode that returns structured JSON

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

## Safety Rules

- Never expose or log the `CLAW_SK` value. When confirming configuration, only show the last 4 characters.
- Input images **must** be in workspace directory for the agent to access them
- Preview images are automatically saved to `workspace/previews/`
- Limit browse results to 10 templates maximum per request

## Examples

```text
User: "I want to make a custom gift for my friend"
→ browse_templates → send the returned table directly
→ user picks → generate_preview → get_generation_status --poll
→ send preview image as media + purchaseUrl in text

User: "Turn this photo into a phone case"
→ browse_templates --category phone → send the returned table directly → user picks
→ generate_preview → get_generation_status --poll
→ send preview image as media + purchaseUrl in text

User: "Show me what products I can customize"
→ browse_templates → send the returned table
```

## Output Structure

### browse_templates
```md
| Image | Product | Price | Template ID | Info | Preview |
| --- | --- | --- | --- | --- | --- |
| ![Men's Hoodie](https://...) | **Men's Hoodie** | **$29.9 USD** | `3` | SKU: hoodie · Ships: CN | [Open image](https://...) |
```
→ Agent sends the markdown table directly so Feishu can render it as a card/table.

### generate_preview --json
```json
{
  "taskId": "task_xxx",
  "status": "PENDING",
  "estimatedSeconds": 45,
  "templateId": 3,
  "_success": true
}
```

### get_generation_status --json (completed)
```json
{
  "taskId": "task_xxx",
  "status": "COMPLETED",
  "purchaseUrl": "https://leewow.com/claw/preview/gen_xxx?skid=...&sig=...",
  "localImagePath": "/Users/.../.openclaw/workspace/previews/leewow_preview_task_xxx.jpg"
}
```
→ Agent sends `localImagePath` as media attachment + `purchaseUrl` in text.
