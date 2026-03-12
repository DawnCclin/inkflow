# InkFlow

基于 GitHub Actions + Python 的多平台技术文章自动发布引擎。

**Write Once, Publish Everywhere** —— 专注写作，发布交给 InkFlow。

在 Obsidian 写好文章，配置好 Front Matter，Push 到 GitHub，剩下的全部自动完成：图片处理、格式适配、多平台并发发布、结果通知。

## 支持平台

| 平台 | 状态 | 实现方式 |
|------|------|---------|
| 掘金 | ✅ 已支持 | Cookie API |
| GitHub Pages | ✅ 已支持 | Git Push（Jekyll） |
| CSDN | 🚧 开发中 | API |
| 微信公众号 | 🚧 开发中 | 草稿 API |
| 知乎 | 📅 规划中 | 创作者 API |

## 工作原理

```
Obsidian 写作
    │
    │  git push（Obsidian Git 插件自动触发）
    ▼
写作仓库（GitHub）
    │
    │  检测到 articles/ 目录下的 .md 变更
    ▼
InkFlow Engine（GitHub Actions）
    │
    ├─ 解析 Front Matter（标题/标签/发布目标）
    ├─ 过滤 status: draft 的文章
    ├─ 并发调度各平台 Skill
    │     ├─ juejin_skill    → 掘金
    │     └─ github_pages_skill → GitHub Pages
    │
    └─ Job Summary 展示发布结果（链接 / 错误详情）
```

## 快速开始

### 第一步：获取掘金 Cookie

1. 浏览器登录 [juejin.cn](https://juejin.cn)
2. 打开 F12 → Application → Cookies → `https://juejin.cn`
3. 找到并复制整行 Cookie 字符串（需包含 `sessionid` 字段）

> Cookie 有效期约 30 天，过期后需重新配置。

### 第二步：创建 GitHub PAT（发布到 GitHub Pages 时需要）

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens**
2. 点击 **Generate new token**
3. Repository access 选择你的 GitHub Pages 仓库
4. Permissions → Repository permissions → **Contents** 设为 **Read and write**
5. 生成并复制 token

### 第三步：配置写作仓库的 Secrets

进入写作仓库 → **Settings → Secrets and variables → Actions → New repository secret**，依次添加：

| Secret 名称 | 说明 | 是否必填 |
|------------|------|---------|
| `JUEJIN_COOKIE` | 掘金登录 Cookie（完整字符串） | 发布掘金时必填 |
| `PAGES_DEPLOY_TOKEN` | GitHub PAT（Contents:write 权限） | 发布 GitHub Pages 时必填 |
| `PAGES_REPO` | Pages 仓库，格式 `用户名/仓库名`（如 `alice/alice.github.io`） | 发布 GitHub Pages 时必填 |
| `PAGES_BRANCH` | Pages 目标分支（默认 `main`，可不填） | 可选 |

### 第四步：添加 Workflow 到写作仓库

在写作仓库中创建 `.github/workflows/publish.yml`，内容如下：

```yaml
name: Publish Articles via InkFlow

on:
  push:
    branches:
      - main
    paths:
      - "articles/**/*.md"
  workflow_dispatch:

jobs:
  publish:
    uses: DawnCclin/inkflow/.github/workflows/engine.yml@main
    with:
      articles_dir: articles
    secrets: inherit
```

> `articles_dir` 改成你仓库中实际存放文章的目录名。

### 第五步：写文章并发布

在写作仓库的 `articles/` 目录下新建 Markdown 文件，头部加上 Front Matter：

```yaml
---
title: 文章标题
description: 文章摘要（建议 50-100 字，掘金摘要要求）
tags: [后端, python, docker]
cover: ./images/cover.png    # 可选，封面图
publish:
  - juejin                   # 发布到掘金
  - githubpages              # 发布到 GitHub Pages
status: published            # draft=草稿不发布 / published=立即发布
date: 2026-03-12
---

正文内容...
```

Push 后 GitHub Actions 自动触发，在 Actions → 对应 workflow run → **Summary** 页面查看发布结果。

## Front Matter 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | 文章标题 |
| `description` | string | 否 | 摘要，建议 50-100 字 |
| `tags` | list | 否 | 标签列表，与各平台标签自动映射 |
| `publish` | list | 是 | 发布目标：`juejin` / `githubpages` |
| `status` | string | 是 | `published` 发布 / `draft` 跳过 |
| `date` | date | 否 | 文章日期，默认当天 |
| `cover` | string | 否 | 封面图路径（Phase 2 支持自动上传 OSS） |
| `slug` | string | 否 | 自定义 URL slug，默认由标题生成 |

## 掘金标签映射

Front Matter 中的 `tags` 会自动映射到掘金标签 ID，当前支持：

`python` / `javascript` / `typescript` / `vue` / `react` / `go` / `java` / `docker` / `k8s` / `linux` / `git` / `mysql` / `redis` / `ai`

不在列表中的标签会被忽略（不影响发布）。如需添加更多标签，参考 [`skills/juejin-publisher/references/tag_ids.md`](skills/juejin-publisher/references/tag_ids.md)，在 [`skills/juejin_skill.py`](skills/juejin_skill.py) 的 `TAG_MAP` 中追加。

## 项目结构

```
DawnCclin/inkflow/
├── .github/workflows/
│   └── engine.yml                 # 可复用 workflow（写作仓库调用此处）
├── agent/
│   ├── models.py                  # 数据模型（Article / PublishResult）
│   ├── preprocessor.py            # Front Matter 解析 + git diff 变更检测
│   ├── orchestrator.py            # asyncio 并发调度器 + CLI 入口
│   └── notifier.py                # GitHub Actions Job Summary 输出
├── skills/
│   ├── base_skill.py              # 抽象基类（publish / update / check_exists）
│   ├── juejin_skill.py            # 掘金发布（Cookie API）
│   └── github_pages_skill.py      # GitHub Pages 发布（Jekyll）
├── examples/
│   ├── writing-repo-publish.yml   # 写作仓库 workflow 模板（直接复制使用）
│   └── sample-article.md          # Front Matter 格式示例
└── requirements.txt
```

## 常见问题

**Q：Push 后 Actions 没有触发？**
检查写作仓库 workflow 的 `paths` 配置，确认文章放在了 `articles/` 目录下，且文件扩展名是 `.md`。

**Q：掘金发布失败，提示 Cookie 过期？**
重新获取 Cookie 后，在写作仓库 Secrets 中更新 `JUEJIN_COOKIE` 的值。

**Q：文章每次 Push 都会重复发布？**
InkFlow 通过 `git diff HEAD~1 HEAD` 只处理本次 Push 变更的文件，未修改的文章不会重复发布。

**Q：想手动触发发布怎么操作？**
进入写作仓库 → Actions → Publish Articles via InkFlow → **Run workflow**。
