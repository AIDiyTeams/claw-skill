# Leewow Skills

## ClawHub Rate Limit Fallback

If ClawHub is rate-limited or unavailable, install this skill directly from GitHub:

- Repository: `https://github.com/AIDiyTeams/claw-skill`
- Skill folder: `custom-gift-leewow`

### Manual Git Install

OpenClaw loads workspace skills from `<workspace>/skills`, so the fallback install is:

```bash
cd /path/to/your/openclaw-workspace
mkdir -p skills
git clone https://github.com/AIDiyTeams/claw-skill.git /tmp/claw-skill
cp -R /tmp/claw-skill/custom-gift-leewow ./skills/custom-gift-leewow
```

### Sparse Checkout Install

If you only want this skill folder:

```bash
cd /path/to/your/openclaw-workspace
mkdir -p skills
git clone --depth 1 --filter=blob:none --sparse https://github.com/AIDiyTeams/claw-skill.git /tmp/claw-skill
cd /tmp/claw-skill
git sparse-checkout set custom-gift-leewow
cp -R /tmp/claw-skill/custom-gift-leewow /path/to/your/openclaw-workspace/skills/custom-gift-leewow
```

### Included Skill

- `custom-gift-leewow`: Browse Leewow product templates and generate custom gift previews.
