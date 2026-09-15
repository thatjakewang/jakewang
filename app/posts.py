"""Category pages for trusted, repository-owned Markdown articles.

Add categories to CATEGORIES, then set title, date and category in front matter.
An optional slug overrides the filename-derived URL. File changes invalidate
the bounded parsing cache; adding or deleting a file needs no process restart.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
import logging
from pathlib import Path
import re

import frontmatter
import markdown
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup
from yaml import YAMLError

from app.templating import BASE_DIR, templates

logger = logging.getLogger(__name__)
POSTS_DIR = BASE_DIR / "posts"
CATEGORIES = {"summaries": "Paper Summaries"}
SEGMENT = re.compile(r"[\w]+(?:-[\w]+)*", re.UNICODE)


@dataclass(frozen=True)
class Post:
    title: str
    date: date
    category: str
    slug: str
    html: Markup
    has_title: bool
    authors: tuple[str, ...]
    venue: str
    doi: str

    @property
    def url(self) -> str:
        return f"/{self.category}/{self.slug}/"


@lru_cache(maxsize=256)
def _read_post(path: Path, mtime_ns: int, size: int) -> Post | None:
    try:
        source = frontmatter.loads(path.read_text(encoding="utf-8-sig"))
        title = source.get("title")
        category = source.get("category")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a nonempty string")
        if not isinstance(category, str) or category not in CATEGORIES:
            raise ValueError("category must name a configured category")
        published = source.get("date")
        if isinstance(published, str):
            published = date.fromisoformat(published)
        if type(published) is not date:
            raise ValueError("date must be YYYY-MM-DD")
        slug = source.get("slug", re.sub(r"[^\w]+", "-", path.stem.lower()).strip("-"))
        if not isinstance(slug, str) or not SEGMENT.fullmatch(slug):
            raise ValueError("slug must contain words separated by hyphens")
        authors = source.get("authors", [])
        if not isinstance(authors, list) or not all(isinstance(a, str) for a in authors):
            raise ValueError("authors must be a list of strings")
        for key in ("venue", "doi"):
            if not isinstance(source.get(key, ""), str):
                raise ValueError(f"{key} must be a string")
        html = markdown.markdown(source.content, extensions=["tables", "fenced_code"], output_format="html")
        # Existing articles may already include their title and bibliographic
        # details. Keep their body intact and only supply missing header fields.
        def included(label: str) -> bool:
            return bool(re.search(rf"<strong>{label}:?</strong>", html, re.IGNORECASE))

        return Post(
            title.strip(), published, category, slug, Markup(html),
            bool(re.search(r"<h1(?:\s|>)", html)),
            () if included("Authors") else tuple(authors),
            "" if included("Venue") else source.get("venue", ""),
            "" if included("DOI") else source.get("doi", ""),
        )
    except (OSError, ValueError, TypeError, YAMLError) as exc:
        logger.warning("Skipping article %s: %s", path, exc)
        return None


def get_posts() -> list[Post]:
    indexed: dict[str, Post] = {}
    duplicates: set[str] = set()
    for path in sorted(POSTS_DIR.rglob("*.md")):
        if not path.resolve().is_relative_to(POSTS_DIR.resolve()):
            continue
        try:
            stat = path.stat()
        except OSError as exc:
            logger.warning("Cannot read article %s: %s", path, exc)
            continue
        post = _read_post(path, stat.st_mtime_ns, stat.st_size)
        if post is None:
            continue
        if post.url in indexed:
            logger.error("Duplicate article URL %s in %s; hiding conflicting articles", post.url, path)
            duplicates.add(post.url)
        indexed[post.url] = post
    return sorted(
        (post for url, post in indexed.items() if url not in duplicates),
        key=lambda post: (post.date, post.slug), reverse=True,
    )


def _category_router(category: str, label: str) -> APIRouter:
    router = APIRouter(prefix=f"/{category}")

    @router.get("/", response_class=HTMLResponse, name=f"{category}_list")
    def post_list(request: Request):
        return templates.TemplateResponse(
            request=request, name="posts.html",
            context={"meta_title": f"{label} – Jake Wang", "category_label": label,
                     "posts": [p for p in get_posts() if p.category == category]},
        )

    @router.get("/{slug}/", response_class=HTMLResponse, name=f"{category}_detail")
    def post_detail(request: Request, slug: str):
        post = next((p for p in get_posts() if p.category == category and p.slug == slug), None)
        if post is None:
            raise HTTPException(status_code=404)
        return templates.TemplateResponse(
            request=request, name="post.html",
            context={"meta_title": f"{post.title} – Jake Wang", "post": post,
                     "category_label": label, "category_url": f"/{category}/"},
        )

    return router


def register_routes(app: FastAPI) -> None:
    """Call after existing routes so reserved URL prefixes can be checked."""
    reserved = {getattr(route, "path", "").strip("/").split("/")[0] for route in app.routes}
    for category, label in CATEGORIES.items():
        if not SEGMENT.fullmatch(category) or category in reserved:
            raise ValueError(f"Invalid or conflicting article category: {category}")
        app.include_router(_category_router(category, label))
