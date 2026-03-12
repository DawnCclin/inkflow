from __future__ import annotations

from abc import ABC, abstractmethod

from agent.models import Article, PublishResult


class BaseSkill(ABC):
    """
    所有平台发布 Skill 的抽象基类。
    子类必须实现 publish() 和 update()。
    check_exists() 用于幂等判断（Phase 2 完整实现）。
    """

    # 子类声明自己对应的平台标识，与 Front Matter publish 字段匹配
    platform: str = ""

    @abstractmethod
    async def publish(self, article: Article) -> PublishResult:
        """将文章首次发布到目标平台，返回发布结果。"""
        ...

    @abstractmethod
    async def update(self, article: Article, article_id: str) -> PublishResult:
        """更新已发布的文章。article_id 为平台侧的文章唯一标识。"""
        ...

    async def check_exists(self, article: Article) -> str | None:
        """
        检查文章是否已在该平台发布。
        返回平台侧 article_id（字符串），未发布则返回 None。
        默认实现始终返回 None（Phase 1 每次都新发布）。
        """
        return None

    async def publish_or_update(self, article: Article) -> PublishResult:
        """
        幂等发布入口：先检查是否已存在，已存在则更新，否则新发布。
        """
        existing_id = await self.check_exists(article)
        if existing_id:
            return await self.update(article, existing_id)
        return await self.publish(article)

    def _make_error_result(self, error: str, retry_count: int = 0) -> PublishResult:
        return PublishResult(
            platform=self.platform,
            success=False,
            error=error,
            retry_count=retry_count,
        )

    def _make_success_result(
        self,
        url: str | None = None,
        article_id: str | None = None,
        retry_count: int = 0,
    ) -> PublishResult:
        return PublishResult(
            platform=self.platform,
            success=True,
            url=url,
            article_id=article_id,
            retry_count=retry_count,
        )
