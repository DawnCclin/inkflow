# InkFlow

基于 GitHub Actions + Python 的多平台技术文章自动发布引擎。

**Write Once, Publish Everywhere** —— 在 Obsidian 写作，Push 即触发多平台发布。

## 支持平台

| 平台 | 状态 | 实现方式 |
|------|------|---------|
| 掘金 | ✅ Phase 1 | Cookie API |
| GitHub Pages | ✅ Phase 1 | Git Push（Jekyll） |
| CSDN | 🚧 Phase 2 | API |
| 微信公众号 | 🚧 Phase 2 | 草稿 API |
| 知乎 | 📅 Phase 3 | 创作者 API |

## 快速开始

### 1. 写作仓库配置

在写作仓库的 **Settings → Secrets → Actions** 中添加：

```
JUEJIN_COOKIE        掘金 Cookie（sessionid=xxx...）
PAGES_DEPLOY_TOKEN   GitHub PAT（Contents:write 权限）
PAGES_REPO           GitHub Pages 仓库（如 alice/alice.github.io）
```

### 2. 添加 Workflow

将 `examples/writing-repo-publish.yml` 复制到写作仓库的 `.github/workflows/publish.yml`。

### 3. 文章 Front Matter 格式

```yaml
---
title: 文章标题
description: 文章摘要（100字以内）
tags: [后端, python, k8s]
cover: ./images/cover.png   # 可选
publish:
  - juejin
  - githubpages
status: published           # draft=不发布 / published=发布
date: 2026-03-12
---
```

### 4. Push 触发发布

```bash
git push origin main
```

GitHub Actions 自动检测变更文章 → 并发发布 → Job Summary 展示结果。

## 项目结构

```
inkflow/
├── .github/workflows/engine.yml   # 可复用 workflow（写作仓库调用此处）
├── agent/
│   ├── models.py                  # 数据模型
│   ├── preprocessor.py            # Front Matter 解析 + 变更检测
│   ├── orchestrator.py            # 发布调度器（CLI 入口）
│   └── notifier.py                # GitHub Actions Summary
├── skills/
│   ├── base_skill.py              # 抽象基类
│   ├── juejin_skill.py            # 掘金
│   └── github_pages_skill.py     # GitHub Pages
├── examples/
│   ├── writing-repo-publish.yml   # 写作仓库 workflow 模板
│   └── sample-article.md         # Front Matter 示例
└── requirements.txt
```
