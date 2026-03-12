from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import frontmatter

from agent.models import Article, PublishStatus


def detect_changed_articles(repo_root: str | Path, articles_dir: str = "articles") -> list[Path]:
    """
    通过 git diff 检测本次 push 中新增或修改的 Markdown 文件。
    仅扫描 articles_dir 目录下的 .md 文件。
    """
    repo_root = Path(repo_root)
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", "HEAD~1", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # 首次提交或只有一个 commit 时，列出所有已追踪的 md 文件
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=AM", "--cached"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []

    changed_files = [
        repo_root / line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith(".md")
        and line.strip().startswith(articles_dir)
    ]

    return [f for f in changed_files if f.exists()]


def load_article(file_path: str | Path) -> Article | None:
    """
    解析 Markdown 文件的 Front Matter，返回 Article 对象。
    Front Matter 缺失必要字段时返回 None。
    """
    file_path = Path(file_path)
    post = frontmatter.load(str(file_path))

    title = post.get("title", "").strip()
    if not title:
        print(f"[preprocessor] 跳过 {file_path.name}：缺少 title")
        return None

    status_raw = post.get("status", "draft")
    try:
        status = PublishStatus(status_raw)
    except ValueError:
        status = PublishStatus.DRAFT

    publish_targets_raw = post.get("publish", [])
    if isinstance(publish_targets_raw, str):
        publish_targets = [publish_targets_raw]
    else:
        publish_targets = list(publish_targets_raw)

    tags_raw = post.get("tags", [])
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    else:
        tags = [str(t) for t in tags_raw]

    description = str(post.get("description", "")).strip()
    cover = post.get("cover")
    pub_date = post.get("date")

    content = _process_content(post.content, file_path.parent)

    return Article(
        title=title,
        content=content,
        description=description,
        tags=tags,
        publish_targets=publish_targets,
        status=status,
        file_path=str(file_path),
        cover=str(cover) if cover else None,
        date=pub_date if hasattr(pub_date, "year") else None,
        slug=post.get("slug"),
    )


def _process_content(content: str, article_dir: Path) -> str:
    """
    对 Markdown 正文做基础预处理：
    - 本地相对图片路径替换占位符（OSS 上传在 Phase 2 实现）
    - 标准化代码块语言标识
    """
    content = _normalize_code_fences(content)
    return content


def _normalize_code_fences(content: str) -> str:
    """将没有语言标识的代码块统一加上 text 标识，避免部分平台渲染异常。"""
    return re.sub(r"^```\s*$", "```text", content, flags=re.MULTILINE)


def load_articles_from_paths(file_paths: list[Path]) -> list[Article]:
    """批量加载文章，过滤掉解析失败的文件。"""
    articles = []
    for path in file_paths:
        article = load_article(path)
        if article is not None:
            articles.append(article)
    return articles


def get_articles_for_publish(
    repo_root: str | Path,
    articles_dir: str = "articles",
) -> list[Article]:
    """
    完整的预处理入口：
    1. 检测变更文件
    2. 解析 Front Matter
    3. 过滤 draft 状态
    4. 过滤没有 publish_targets 的文章
    """
    changed_paths = detect_changed_articles(repo_root, articles_dir)
    if not changed_paths:
        print("[preprocessor] 本次 push 无变更的 Markdown 文章")
        return []

    articles = load_articles_from_paths(changed_paths)

    publishable = [
        a for a in articles
        if a.should_publish and a.publish_targets
    ]

    skipped = len(articles) - len(publishable)
    if skipped:
        print(f"[preprocessor] 跳过 {skipped} 篇文章（draft 或未指定发布目标）")

    print(f"[preprocessor] 待发布文章：{len(publishable)} 篇")
    return publishable
