import os
from datetime import date

import pytest

from app.posts import _read_post
from app.templating import NO_DATA, money, number


def read(tmp_path, front_matter, body="Hello.", name="my-post.md"):
    path = tmp_path / name
    path.write_text(f"---\n{front_matter}\n---\n\n{body}\n", encoding="utf-8")
    stat = os.stat(path)
    return _read_post(path, stat.st_mtime_ns, stat.st_size)


VALID = "title: A Post\ndate: 2026-11-04\ncategory: kintone"


def test_valid_post_uses_the_filename_as_slug(tmp_path):
    post = read(tmp_path, VALID, name="My Post.md")
    assert (post.title, post.date, post.slug) == ("A Post", date(2026, 11, 4), "my-post")
    assert post.url == "/kintone/my-post/"
    assert not post.has_title


def test_slug_and_tags_from_front_matter(tmp_path):
    post = read(tmp_path, VALID + "\nslug: custom-slug\ntags: [JavaScript, CSS, JavaScript]")
    assert post.slug == "custom-slug"
    assert post.tags == ("JavaScript", "CSS")


def test_body_h1_is_detected(tmp_path):
    assert read(tmp_path, VALID, body="# Heading").has_title


@pytest.mark.parametrize("front_matter", [
    "date: 2026-11-04\ncategory: kintone",                      # no title
    "title: A Post\ndate: 2026-11-04\ncategory: nope",          # unknown category
    "title: A Post\ndate: someday\ncategory: kintone",          # bad date
    "title: A Post\ncategory: kintone",                         # no date
    VALID + "\nslug: Not A Slug!",
    VALID + "\ntags: JavaScript",                               # not a list
    "title: [unclosed",                                         # broken YAML
])
def test_invalid_posts_are_skipped(tmp_path, front_matter):
    assert read(tmp_path, front_matter) is None


def test_number_and_money_filters():
    assert number(None) == NO_DATA
    assert number(1234.0, " km") == "1,234 km"
    assert number(15.2) == "15.2"
    assert money(25000) == "NT$ 25,000"
    assert money(3.5, suffix="/kWh") == "NT$ 3.5/kWh"
    assert money(None, "No paid sessions") == "No paid sessions"
