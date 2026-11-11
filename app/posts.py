"""Category pages for trusted, repository-owned Markdown articles.

Add categories to CATEGORIES, then set title, date and category in front matter.
An optional slug overrides the filename-derived URL, optional tags label
the article in category lists, an optional description replaces the first
paragraph as the meta description, and an optional updated date records the
last revision. File changes invalidate the bounded parsing
cache; adding or deleting a file needs no process restart.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
import html as html_lib
import logging
from pathlib import Path
import re

import frontmatter
import markdown
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup
from yaml import YAMLError

from app.templating import BASE_DIR, absolute_url, templates

logger = logging.getLogger(__name__)
POSTS_DIR = BASE_DIR / "posts"
CATEGORIES = {"kintone": "Kintone"}
# Heading (<h1> and <title>) and meta description for each category's list
# page. The short label above stays the name used in navigation and badges.
CATEGORY_HEADINGS = {"kintone": "Kintone JavaScript Customization Guides"}
CATEGORY_DESCRIPTIONS = {
    "kintone": "Short how-to posts on customizing Kintone apps with JavaScript and CSS.",
}
# Search results show roughly this many characters of a meta description.
DESCRIPTION_LIMIT = 160
# The articles are the one part of the site meant to be found by search. The
# header overrides the site-wide noindex default set in app/main.py, and the
# `indexable` context flag does the same for the <meta> tag in base.html.
# Only the two 200 responses below carry them, so a 404 here stays noindex.
INDEXABLE_HEADERS = {"X-Robots-Tag": "all"}
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
    tags: tuple[str, ...]
    description: str
    updated: date

    @property
    def url(self) -> str:
        return f"/{self.category}/{self.slug}/"


def _first_paragraph(html: str) -> str:
    """The first paragraph as plain text, for the meta description.

    Kept to the leading sentences that fit in DESCRIPTION_LIMIT, so the
    snippet ends on a full stop instead of being cut off by the search engine.
    """
    match = re.search(r"<p>(.*?)</p>", html, re.DOTALL)
    if match is None:
        return ""
    text = " ".join(html_lib.unescape(re.sub(r"<[^>]+>", "", match.group(1))).split())
    summary = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(summary) + len(sentence) + 1 > DESCRIPTION_LIMIT:
            break
        summary = f"{summary} {sentence}".strip()
    if summary:
        return summary
    if len(text) <= DESCRIPTION_LIMIT:
        return text
    return text[:DESCRIPTION_LIMIT].rsplit(" ", 1)[0] + "…"


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
        updated = source.get("updated", published)
        if isinstance(updated, str):
            updated = date.fromisoformat(updated)
        if type(updated) is not date or updated < published:
            raise ValueError("updated must be YYYY-MM-DD, on or after date")
        slug = source.get("slug", re.sub(r"[^\w]+", "-", path.stem.lower()).strip("-"))
        if not isinstance(slug, str) or not SEGMENT.fullmatch(slug):
            raise ValueError("slug must contain words separated by hyphens")
        authors = source.get("authors", [])
        if not isinstance(authors, list) or not all(isinstance(a, str) for a in authors):
            raise ValueError("authors must be a list of strings")
        tags = source.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(t, str) and t.strip() for t in tags):
            raise ValueError("tags must be a list of nonempty strings")
        for key in ("venue", "doi", "description"):
            if not isinstance(source.get(key, ""), str):
                raise ValueError(f"{key} must be a string")
        html = markdown.markdown(
            source.content, extensions=["tables", "fenced_code", "codehilite"],
            extension_configs={"codehilite": {"guess_lang": False}}, output_format="html",
        )
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
            tuple(dict.fromkeys(t.strip() for t in tags)),
            source.get("description", "").strip() or _first_paragraph(html),
            updated,
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


def _structured_data(post: Post, label: str) -> dict:
    """schema.org JSON-LD for an article: the post itself and its breadcrumb."""
    url = absolute_url(post.url)
    authors = post.authors or ("Jake Wang",)
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BlogPosting",
                "headline": post.title,
                "description": post.description,
                "datePublished": post.date.isoformat(),
                "dateModified": post.updated.isoformat(),
                "url": url,
                "mainEntityOfPage": url,
                "inLanguage": "en",
                "keywords": list(post.tags),
                "author": [{"@type": "Person", "name": name} for name in authors],
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": label,
                     "item": absolute_url(f"/{post.category}/")},
                    {"@type": "ListItem", "position": 2, "name": post.title, "item": url},
                ],
            },
        ],
    }


def _category_router(category: str, label: str) -> APIRouter:
    router = APIRouter(prefix=f"/{category}")

    @router.get("/", response_class=HTMLResponse, name=f"{category}_list")
    def post_list(request: Request):
        heading = CATEGORY_HEADINGS.get(category, label)
        return templates.TemplateResponse(
            request=request, name="posts.html", headers=INDEXABLE_HEADERS,
            context={"meta_title": f"{heading} – Jake Wang", "category_label": label,
                     "heading": heading,
                     "meta_description": CATEGORY_DESCRIPTIONS.get(category, ""),
                     "indexable": True,
                     "posts": [p for p in get_posts() if p.category == category]},
        )

    @router.get("/{slug}/", response_class=HTMLResponse, name=f"{category}_detail")
    def post_detail(request: Request, slug: str):
        post = next((p for p in get_posts() if p.category == category and p.slug == slug), None)
        if post is None:
            raise HTTPException(status_code=404)
        return templates.TemplateResponse(
            request=request, name="post.html", headers=INDEXABLE_HEADERS,
            # No site-name suffix: the title alone already fills what a
            # search result shows.
            context={"meta_title": post.title, "post": post,
                     "og_type": "article",
                     "meta_description": post.description,
                     "structured_data": _structured_data(post, label),
                     "indexable": True,
                     "category_label": label, "category_url": f"/{category}/"},
        )

    return router


def sitemap_entries() -> list[tuple[str, date]]:
    """(path, last modified) for every indexable page: each category list that
    has articles, dated by its latest change, then the articles themselves."""
    all_posts = get_posts()
    entries = []
    for category in CATEGORIES:
        newest = max((p.updated for p in all_posts if p.category == category), default=None)
        if newest is not None:
            entries.append((f"/{category}/", newest))
    entries.extend((post.url, post.updated) for post in all_posts)
    return entries


def register_routes(app: FastAPI) -> None:
    """Call after existing routes so reserved URL prefixes can be checked."""
    reserved = {getattr(route, "path", "").strip("/").split("/")[0] for route in app.routes}
    for category, label in CATEGORIES.items():
        if not SEGMENT.fullmatch(category) or category in reserved:
            raise ValueError(f"Invalid or conflicting article category: {category}")
        app.include_router(_category_router(category, label))
