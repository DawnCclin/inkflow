from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class PublishStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Platform(str, Enum):
    JUEJIN = "juejin"
    GITHUB_PAGES = "githubpages"
    CSDN = "csdn"
    WECHAT = "wechat"
    ZHIHU = "zhihu"


@dataclass
class Article:
    title: str
    content: str
    description: str
    tags: list[str]
    publish_targets: list[str]
    status: PublishStatus
    file_path: str
    cover: str | None = None
    date: date | None = None
    slug: str | None = None

    @property
    def should_publish(self) -> bool:
        return self.status == PublishStatus.PUBLISHED

    @property
    def filename_slug(self) -> str:
        if self.slug:
            return self.slug
        safe = self.title.lower()
        for ch in " \t/\\:*?\"<>|":
            safe = safe.replace(ch, "-")
        return safe.strip("-")

    @property
    def jekyll_filename(self) -> str:
        pub_date = self.date or date.today()
        return f"{pub_date.strftime('%Y-%m-%d')}-{self.filename_slug}.md"


@dataclass
class PublishResult:
    platform: str
    success: bool
    url: str | None = None
    error: str | None = None
    article_id: str | None = None
    retry_count: int = 0


@dataclass
class PublishReport:
    results: list[PublishResult] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)
