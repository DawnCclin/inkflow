from __future__ import annotations

import os
import re

import httpx

from agent.models import Article, PublishResult
from skills.base_skill import BaseSkill

BASE_URL = "https://api.juejin.cn/content_api/v1"

# 掘金分类 ID 映射（来源：skills/juejin-publisher/references/category_ids.md）
CATEGORY_MAP: dict[str, str] = {
    "前端": "6809637767543259144",
    "后端": "6809637769959178254",
    "android": "6809635626879549454",
    "ios": "6809635627209637895",
    "ai": "6809637773935378440",
    "工具": "6809637771511070734",
    "阅读": "6809637772874219534",
    "开源": "6809637775100469261",
    "default": "6809637769959178254",
}

# 掘金标签 ID 映射（来源：skills/juejin-publisher/references/tag_ids.md）
TAG_MAP: dict[str, str] = {
    "python": "6809640408797167623",
    "javascript": "6809640407484334093",
    "typescript": "6809640445233070094",
    "vue": "6809640445233070095",
    "vue.js": "6809640445233070095",
    "react": "6809640407484334100",
    "node.js": "6809640408797167624",
    "nodejs": "6809640408797167624",
    "go": "6809640408797167625",
    "java": "6809640408797167626",
    "docker": "6809640445233070096",
    "k8s": "6809640445233070097",
    "kubernetes": "6809640445233070097",
    "ai": "6809640445233070098",
    "chatgpt": "6809640445233070099",
    "linux": "6809640407484334101",
    "git": "6809640407484334102",
    "mysql": "6809640407484334103",
    "redis": "6809640407484334104",
}


def _generate_brief(description: str, content: str, min_len: int = 50, max_len: int = 100) -> str:
    """
    生成符合掘金要求的摘要（50-100字）。
    逻辑与 juejin-publisher/scripts/publish.py 的 generate_brief 对齐。
    """
    if description:
        if min_len <= len(description) <= max_len:
            return description
        if len(description) > max_len:
            return description[:max_len]
        plain = re.sub(r"[#*`>\[\]!]", "", content)
        plain = re.sub(r"\s+", " ", plain).strip()
        combined = (description + " " + plain)[:max_len]
        return combined

    plain = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    plain = re.sub(r"[#*`>\[\]!]", "", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) < min_len:
        return plain.ljust(min_len)
    return plain[:max_len]


class JuejinSkill(BaseSkill):
    platform = "juejin"

    def __init__(self, cookie: str | None = None) -> None:
        self._cookie = cookie or os.environ.get("JUEJIN_COOKIE", "")
        if not self._cookie:
            raise ValueError("JUEJIN_COOKIE 未配置，无法发布到掘金")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Cookie": self._cookie,
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://juejin.cn/",
            "Origin": "https://juejin.cn",
        }

    def _resolve_category_id(self, tags: list[str]) -> str:
        for tag in tags:
            cid = CATEGORY_MAP.get(tag.lower())
            if cid:
                return cid
        return CATEGORY_MAP["default"]

    def _resolve_tag_ids(self, tags: list[str]) -> list[str]:
        return [TAG_MAP[t.lower()] for t in tags if t.lower() in TAG_MAP]

    async def publish(self, article: Article) -> PublishResult:
        async with httpx.AsyncClient(timeout=30) as client:
            draft_id = await self._create_draft(client, article)
            if draft_id is None:
                return self._make_error_result("创建草稿失败")

            url = await self._publish_draft(client, draft_id)
            if url is None:
                return self._make_error_result(f"发布草稿失败，draft_id={draft_id}")

            return self._make_success_result(url=url, article_id=draft_id)

    async def update(self, article: Article, article_id: str) -> PublishResult:
        async with httpx.AsyncClient(timeout=30) as client:
            ok = await self._update_draft(client, article_id, article)
            if not ok:
                return self._make_error_result(f"更新草稿失败，draft_id={article_id}")

            url = await self._publish_draft(client, article_id)
            if url is None:
                return self._make_error_result(f"重新发布失败，draft_id={article_id}")

            return self._make_success_result(url=url, article_id=article_id)

    async def _create_draft(self, client: httpx.AsyncClient, article: Article) -> str | None:
        brief = _generate_brief(article.description, article.content)
        payload = {
            "category_id": self._resolve_category_id(article.tags),
            "tag_ids": self._resolve_tag_ids(article.tags),
            "link_url": "",
            "cover_image": article.cover or "",
            "title": article.title,
            "brief_content": brief,
            "edit_type": 10,
            "html_content": "deprecated",
            "mark_content": article.content,
            "theme_ids": [],
        }
        resp = await client.post(
            f"{BASE_URL}/article_draft/create",
            json=payload,
            headers=self._headers,
        )
        data = resp.json()
        if data.get("err_no") != 0:
            print(f"[juejin] 创建草稿失败: {data.get('err_msg')} (err_no={data.get('err_no')})")
            return None
        draft_id = data["data"]["id"]
        print(f"[juejin] 草稿创建成功，draft_id: {draft_id}")
        return draft_id

    async def _update_draft(
        self, client: httpx.AsyncClient, draft_id: str, article: Article
    ) -> bool:
        brief = _generate_brief(article.description, article.content)
        payload = {
            "id": draft_id,
            "category_id": self._resolve_category_id(article.tags),
            "tag_ids": self._resolve_tag_ids(article.tags),
            "cover_image": article.cover or "",
            "title": article.title,
            "brief_content": brief,
            "edit_type": 10,
            "html_content": "deprecated",
            "mark_content": article.content,
            "theme_ids": [],
        }
        resp = await client.post(
            f"{BASE_URL}/article_draft/update",
            json=payload,
            headers=self._headers,
        )
        data = resp.json()
        if data.get("err_no") != 0:
            print(f"[juejin] 更新草稿失败: {data.get('err_msg')} (err_no={data.get('err_no')})")
            return False
        return True

    async def _publish_draft(self, client: httpx.AsyncClient, draft_id: str) -> str | None:
        payload = {
            "draft_id": draft_id,
            "sync_to_org": False,
            "column_ids": [],
            "theme_ids": [],
        }
        resp = await client.post(
            f"{BASE_URL}/article/publish",
            json=payload,
            headers=self._headers,
        )
        data = resp.json()
        if data.get("err_no") != 0:
            print(f"[juejin] 发布失败: {data.get('err_msg')} (err_no={data.get('err_no')})")
            return None
        article_id = data["data"]["article_id"]
        url = f"https://juejin.cn/post/{article_id}"
        print(f"[juejin] 发布成功！{url}")
        return url
