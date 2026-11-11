import os
from datetime import date

import pytest

from app.posts import _read_post, related_posts
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


def test_description_defaults_to_the_first_paragraph(tmp_path):
    post = read(tmp_path, VALID, body="## Heading\n\nUse `a < b` & *save*.\n\nSecond.")
    assert post.description == "Use a < b & save."


def test_long_description_keeps_whole_sentences(tmp_path):
    body = "One short sentence. " + "word " * 40 + "end."
    assert read(tmp_path, VALID, body=body).description == "One short sentence."
    cut = read(tmp_path, VALID, body="word " * 50).description
    assert len(cut) <= 161 and cut.endswith("…")


def test_description_from_front_matter(tmp_path):
    assert read(tmp_path, VALID + "\ndescription: Short summary.").description == "Short summary."


def test_updated_defaults_to_the_publish_date(tmp_path):
    assert read(tmp_path, VALID).updated == date(2026, 11, 4)
    assert read(tmp_path, VALID + "\nupdated: 2026-11-10").updated == date(2026, 11, 10)


def test_related_posts_prefer_shared_tags_and_skip_linked_ones(tmp_path):
    def make(slug, tags, day, body="Hello."):
        front = f"title: {slug}\ndate: 2026-11-{day:02d}\ncategory: kintone\ntags: [{tags}]"
        return read(tmp_path, front, body=body, name=f"{slug}.md")

    post = make("post", "Forms, CSS", 1, body="See [linked](/kintone/linked/).")
    others = [make("linked", "Forms, CSS", 2), make("one-tag", "Forms", 3),
              make("two-tags", "CSS, Forms", 4), make("newest", "Other", 9),
              make("older", "Other", 5)]
    related = related_posts(post, [post, *others])
    assert [p.slug for p in related] == ["two-tags", "one-tag", "newest"]


def test_body_h1_is_detected(tmp_path):
    assert read(tmp_path, VALID, body="# Heading").has_title


@pytest.mark.parametrize("front_matter", [
    "date: 2026-11-04\ncategory: kintone",                      # no title
    "title: A Post\ndate: 2026-11-04\ncategory: nope",          # unknown category
    "title: A Post\ndate: someday\ncategory: kintone",          # bad date
    "title: A Post\ncategory: kintone",                         # no date
    VALID + "\nslug: Not A Slug!",
    VALID + "\nupdated: 2026-11-01",                            # before the publish date
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
