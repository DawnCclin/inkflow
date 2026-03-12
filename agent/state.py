from __future__ import annotations

import json
import os
from pathlib import Path

from agent.models import Article, PublishResult

STATE_FILENAME = ".inkflow-state.json"


def _state_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / STATE_FILENAME


def load_state(repo_root: str | Path) -> dict:
    """
    加载发布状态文件。
    结构：{ "articles/post.md::juejin": "https://juejin.cn/post/xxx" }
    """
    path = _state_path(repo_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(repo_root: str | Path, state: dict) -> None:
    path = _state_path(repo_root)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def state_key(article: Article, platform: str) -> str:
    return f"{article.file_path}::{platform}"


def is_published(state: dict, article: Article, platform: str) -> bool:
    return state_key(article, platform) in state


def record_result(state: dict, article: Article, result: PublishResult) -> None:
    if result.success:
        state[state_key(article, result.platform)] = result.url or ""
