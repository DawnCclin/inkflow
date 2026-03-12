from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agent.models import Article, Platform, PublishReport, PublishResult
from agent.notifier import print_summary_to_console, write_job_summary
from agent.preprocessor import get_articles_for_publish
from skills.base_skill import BaseSkill
from skills.github_pages_skill import GitHubPagesSkill
from skills.juejin_skill import JuejinSkill


def _build_skill_registry() -> dict[str, BaseSkill]:
    """
    按需初始化 Skill 实例。
    Skill 初始化失败（缺少密钥）时打印警告并跳过，不中断整体流程。
    """
    registry: dict[str, BaseSkill] = {}

    skill_factories: dict[str, type[BaseSkill]] = {
        Platform.JUEJIN: JuejinSkill,
        Platform.GITHUB_PAGES: GitHubPagesSkill,
    }

    for platform, skill_cls in skill_factories.items():
        try:
            registry[platform] = skill_cls()
        except ValueError as e:
            print(f"[orchestrator] 跳过 {platform}：{e}")

    return registry


async def _publish_with_retry(
    skill: BaseSkill,
    article: Article,
    max_attempts: int = 3,
) -> PublishResult:
    """
    带指数退避重试的发布函数。
    每次重试间隔：2s → 4s → 8s。
    """
    attempt = 0

    for attempt in range(1, max_attempts + 1):
        try:
            result = await skill.publish_or_update(article)
            result.retry_count = attempt - 1
            if result.success:
                return result
            if attempt < max_attempts:
                wait = 2 ** attempt
                print(
                    f"[orchestrator] {skill.platform} 发布失败，"
                    f"{wait}s 后重试 ({attempt}/{max_attempts}): {result.error}"
                )
                await asyncio.sleep(wait)
        except Exception as e:
            if attempt < max_attempts:
                wait = 2 ** attempt
                print(
                    f"[orchestrator] {skill.platform} 发生异常，"
                    f"{wait}s 后重试 ({attempt}/{max_attempts}): {e}"
                )
                await asyncio.sleep(wait)
            else:
                return PublishResult(
                    platform=skill.platform,
                    success=False,
                    error=str(e),
                    retry_count=attempt - 1,
                )

    return PublishResult(
        platform=skill.platform,
        success=False,
        error="超过最大重试次数",
        retry_count=max_attempts - 1,
    )


async def run_publish_pipeline(
    articles: list[Article],
    skill_registry: dict[str, BaseSkill],
) -> PublishReport:
    """
    并发调度所有 (文章 × 平台) 发布任务，返回汇总报告。
    """
    tasks: list[tuple[str, asyncio.Task[PublishResult]]] = []

    for article in articles:
        for platform in article.publish_targets:
            skill = skill_registry.get(platform)
            if skill is None:
                print(f"[orchestrator] 未找到 {platform} 的 Skill，跳过《{article.title}》")
                continue
            print(f"[orchestrator] 排队：{platform} ← 《{article.title}》")
            task = asyncio.create_task(
                _publish_with_retry(skill, article),
                name=f"{platform}:{article.title}",
            )
            tasks.append((platform, task))

    if not tasks:
        print("[orchestrator] 无有效发布任务")
        return PublishReport()

    results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=False)
    return PublishReport(results=list(results))


def main() -> int:
    repo_root = os.environ.get("GITHUB_WORKSPACE") or str(Path.cwd())
    articles_dir = os.environ.get("INKFLOW_ARTICLES_DIR", "articles")

    print(f"[orchestrator] 仓库路径：{repo_root}")
    print(f"[orchestrator] 文章目录：{articles_dir}")

    articles = get_articles_for_publish(repo_root, articles_dir)
    if not articles:
        print("[orchestrator] 无待发布文章，退出")
        return 0

    skill_registry = _build_skill_registry()
    if not skill_registry:
        print("[orchestrator] 没有可用的发布 Skill（检查 GitHub Secrets 配置）")
        return 1

    report = asyncio.run(run_publish_pipeline(articles, skill_registry))

    print_summary_to_console(report)
    write_job_summary(report, articles)

    return 0 if report.all_succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
