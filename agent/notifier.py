from __future__ import annotations

import os
from datetime import datetime, timezone

from agent.models import Article, PublishReport, PublishResult


_STATUS_ICON = {True: "✅ 成功", False: "❌ 失败"}


def write_job_summary(report: PublishReport, articles: list[Article]) -> None:
    """
    将发布结果写入 GitHub Actions Job Summary（$GITHUB_STEP_SUMMARY）。
    本地运行时输出到 stdout。
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    content = _build_summary(report, articles)

    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(content)
    else:
        print(content)


def _build_summary(report: PublishReport, articles: list[Article]) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "## InkFlow 发布结果\n",
        f"> 发布时间：{now}  ",
        f"> 文章总数：{len(articles)}  ",
        f"> 成功：{report.success_count}  失败：{report.failure_count}\n",
    ]

    if not report.results:
        lines.append("_本次 push 无需发布的文章。_\n")
        return "\n".join(lines)

    # 按文章分组展示
    results_by_article: dict[str, list[PublishResult]] = {}
    article_map = {a.file_path: a for a in articles}

    for result in report.results:
        key = result.platform  # fallback grouping
        results_by_article.setdefault(key, []).append(result)

    # 如果有文章信息，按文章分组
    if articles:
        article_results: dict[str, list[PublishResult]] = {
            a.title: [] for a in articles
        }
        for result in report.results:
            # result 中暂无 article_title，所以平铺展示
            pass

    lines.append("| 平台 | 状态 | 重试次数 | 链接 |")
    lines.append("|------|------|---------|------|")

    for result in report.results:
        status = _STATUS_ICON[result.success]
        link = f"[查看]({result.url})" if result.url else "-"
        retry = str(result.retry_count) if result.retry_count else "0"
        lines.append(f"| {result.platform} | {status} | {retry} | {link} |")

    if report.failure_count > 0:
        lines.append("\n### 失败详情\n")
        for result in report.results:
            if not result.success and result.error:
                lines.append(f"- **{result.platform}**: {result.error}")

    lines.append("")
    return "\n".join(lines)


def print_summary_to_console(report: PublishReport) -> None:
    """在 CI 日志中打印简洁的发布摘要。"""
    print("\n" + "=" * 50)
    print("InkFlow 发布完成")
    print("=" * 50)
    for result in report.results:
        icon = "✅" if result.success else "❌"
        url_str = f" → {result.url}" if result.url else ""
        retry_str = f" (重试 {result.retry_count} 次)" if result.retry_count else ""
        print(f"  {icon} {result.platform}{url_str}{retry_str}")
        if not result.success and result.error:
            print(f"     错误：{result.error}")
    print("=" * 50 + "\n")
