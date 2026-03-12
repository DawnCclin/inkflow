from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from agent.models import Article, PublishResult
from skills.base_skill import BaseSkill


class GitHubPagesSkill(BaseSkill):
    """
    将文章推送到目标 GitHub Pages 仓库的 Jekyll _posts 目录。

    所需环境变量：
      PAGES_DEPLOY_TOKEN  - GitHub PAT (contents:write 权限)
      PAGES_REPO          - 目标仓库，格式 owner/repo（如 alice/alice.github.io）
      PAGES_BRANCH        - 目标分支，默认 main（gh-pages 站点通常在 main 或 gh-pages）
      GIT_USER_NAME       - commit 显示名，默认 InkFlow Bot
      GIT_USER_EMAIL      - commit 邮箱，默认 inkflow-bot@github.com
    """

    platform = "githubpages"

    def __init__(
        self,
        token: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
    ) -> None:
        self._token = token or os.environ.get("PAGES_DEPLOY_TOKEN", "")
        self._repo = repo or os.environ.get("PAGES_REPO", "")
        self._branch = branch or os.environ.get("PAGES_BRANCH", "main")
        self._git_name = os.environ.get("GIT_USER_NAME", "InkFlow Bot")
        self._git_email = os.environ.get("GIT_USER_EMAIL", "inkflow-bot@github.com")

        if not self._token:
            raise ValueError("PAGES_DEPLOY_TOKEN 未配置，无法推送到 GitHub Pages")
        if not self._repo:
            raise ValueError("PAGES_REPO 未配置（格式：owner/repo）")

    @property
    def _clone_url(self) -> str:
        return f"https://x-access-token:{self._token}@github.com/{self._repo}.git"

    @property
    def _pages_url(self) -> str:
        owner = self._repo.split("/")[0]
        repo_name = self._repo.split("/")[-1]
        if repo_name == f"{owner}.github.io":
            return f"https://{owner}.github.io"
        return f"https://{owner}.github.io/{repo_name}"

    async def publish(self, article: Article) -> PublishResult:
        return self._push_article(article)

    async def update(self, article: Article, article_id: str) -> PublishResult:
        # GitHub Pages 通过文件名幂等，直接覆盖推送即可
        return self._push_article(article)

    def _push_article(self, article: Article) -> PublishResult:
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                self._clone(tmpdir)
                filename = article.jekyll_filename
                dest_path = Path(tmpdir) / "_posts" / filename
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(
                    self._build_post_content(article), encoding="utf-8"
                )
                self._git_commit_push(tmpdir, filename)
                url = f"{self._pages_url}/{article.filename_slug}/"
                return self._make_success_result(url=url, article_id=filename)
            except subprocess.CalledProcessError as e:
                return self._make_error_result(
                    f"git 操作失败: {e.stderr or e.stdout or str(e)}"
                )
            except Exception as e:
                return self._make_error_result(str(e))

    def _clone(self, tmpdir: str) -> None:
        subprocess.run(
            [
                "git", "clone",
                "--depth", "1",
                "--branch", self._branch,
                self._clone_url,
                tmpdir,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def _git_commit_push(self, repo_dir: str, filename: str) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": self._git_name,
            "GIT_AUTHOR_EMAIL": self._git_email,
            "GIT_COMMITTER_NAME": self._git_name,
            "GIT_COMMITTER_EMAIL": self._git_email,
        }

        subprocess.run(
            ["git", "config", "user.name", self._git_name],
            cwd=repo_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", self._git_email],
            cwd=repo_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "add", f"_posts/{filename}"],
            cwd=repo_dir, check=True, capture_output=True, env=env,
        )
        subprocess.run(
            ["git", "commit", "-m", f"docs: publish {filename} via InkFlow"],
            cwd=repo_dir, check=True, capture_output=True, env=env,
        )
        subprocess.run(
            ["git", "push", "origin", self._branch],
            cwd=repo_dir, check=True, capture_output=True, env=env,
        )

    @staticmethod
    def _build_post_content(article: Article) -> str:
        """构建带 Jekyll Front Matter 的文章内容。"""
        from datetime import date as date_type
        import yaml

        pub_date = article.date or date_type.today()
        front_matter: dict = {
            "layout": "post",
            "title": article.title,
            "date": pub_date.strftime("%Y-%m-%d %H:%M:%S +0000"),
            "tags": article.tags,
        }
        if article.description:
            front_matter["excerpt"] = article.description
        if article.cover:
            front_matter["cover"] = article.cover

        fm_str = yaml.dump(
            front_matter,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).strip()

        return f"---\n{fm_str}\n---\n\n{article.content}\n"
