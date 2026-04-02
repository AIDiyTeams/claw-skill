---
name: publish-leewow-skill
description: 在 leewow-skills 仓库发布 skill 到 GitHub main 和 ClawHub 时使用。适用于“帮我发版这个 skill”“同步发布到 git 和 clawhub”“更新版本号后做双渠道发布”等场景。默认面向 /Users/apple/LeeWoW/leewow-skills 下的 skill，例如 custom-gift-leewow。
---

# 发布 leewow skill

用于把 `leewow-skills` 仓库里的某个 skill 同步发布到两个渠道：

- GitHub `main`
- ClawHub 指定版本

## 何时使用

- 用户要求把某个 skill 同时发布到 GitHub 和 ClawHub
- 用户要求 bump 版本号后发版
- 用户要求“同步两个渠道”“发到 git 和 clawhub”

## 默认范围

- 仓库：`/Users/apple/LeeWoW/leewow-skills`
- 默认 skill：`custom-gift-leewow`
- 如果用户明确指定了其他 skill 文件夹，按用户指定处理

## 核心步骤

### 1. 确认版本号一致

先检查目标 skill 的：

- `SKILL.md` frontmatter 里的 `version`
- 文末 `Version Marker`

两者必须一致后再发布。

示例：

```bash
rg -n "^version:|Version Marker:" /Users/apple/LeeWoW/leewow-skills/custom-gift-leewow/SKILL.md
```

### 2. 做最小验证

按改动内容做最小验证：

- Python 脚本有改动：优先跑 `python3 -m py_compile`
- 文档-only 改动：至少检查版本号和关键路径
- 如果做了额外本地 smoke test，在最终汇报里说明

示例：

```bash
python3 -m py_compile /Users/apple/LeeWoW/leewow-skills/custom-gift-leewow/scripts/browse.py
```

### 3. 发布到 GitHub

在 `leewow-skills` 仓库内：

```bash
cd /Users/apple/LeeWoW/leewow-skills
git status -sb
git add <changed-files>
git commit -m "feat|fix|docs|perf: concise summary"
git push origin main
```

要求：

- 使用 Conventional Commits
- 不要跳过 hooks
- 推送后再确认 `main...origin/main` 已同步

### 4. 发布到 ClawHub

在这台机器上，ClawHub CLI 可能有本地 TLS 证书链问题。默认使用这个命令：

```bash
cd /Users/apple/LeeWoW/leewow-skills
NODE_TLS_REJECT_UNAUTHORIZED=0 npx -y clawhub publish /Users/apple/LeeWoW/leewow-skills/custom-gift-leewow --version 1.0.24
```

把其中：

- skill 路径替换成目标 skill
- `--version` 替换成 `SKILL.md` 中的当前版本

如果用户指定了其他 skill，同样替换路径。

### 5. 汇报发布结果

最终回复至少包含：

- GitHub 是否已推送到 `main`
- 最新 commit hash
- ClawHub 发布版本号
- ClawHub 发布 ID
- 如果用了 `NODE_TLS_REJECT_UNAUTHORIZED=0`，要简短说明这是本机发布链路 workaround，不是 skill 本身改动

## 常用命令模板

```bash
cd /Users/apple/LeeWoW/leewow-skills
git log --oneline --decorate -5
git status -sb
rg -n "^version:|Version Marker:" /Users/apple/LeeWoW/leewow-skills/custom-gift-leewow/SKILL.md
NODE_TLS_REJECT_UNAUTHORIZED=0 npx -y clawhub publish /Users/apple/LeeWoW/leewow-skills/custom-gift-leewow --version <version>
```

## 使用原则

- 发布顺序默认是：先 GitHub，再 ClawHub
- 不要发布版本号不一致的 skill
- 不要把根目录 `/Users/apple/LeeWoW/.cursor` 下的内部文件当作可提交内容；可提交的内部 skill 优先放在仓库内的 `.cursor/skills`
