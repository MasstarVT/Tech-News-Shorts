from datetime import UTC, datetime

from technews.config import FeedConfig
from technews.models import Story
from technews.news import history
from technews.news.rank import cluster, excluded, rank
from technews.news.sources import html_to_text, parse_feed, site_name

from .conftest import FIXTURES

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def load(cfg):
    a = parse_feed((FIXTURES / "feed_verge.xml").read_bytes(), FeedConfig(name="Sample Feed A", url="x"))
    b = parse_feed((FIXTURES / "feed_ars.xml").read_bytes(), FeedConfig(name="Sample Feed B", url="y"))
    return a + b


def test_parse_atom_and_rss(cfg):
    stories = load(cfg)
    titles = [s.title for s in stories]
    assert "Chipmaker unveils a faster laptop processor" in titles
    chip_b = next(s for s in stories if s.url == "https://example.org/b/chip")
    assert chip_b.published == datetime(2026, 10, 20, 7, 30, tzinfo=UTC)
    assert "3 nanometer" in chip_b.text  # content:encoded carried the full article
    chip_a = stories[0]
    assert chip_a.summary.startswith("The new processor is 30% faster")


def test_exclusions(cfg):
    deals = Story(id="1", title="The best laptop deals this week", url="u", source="s")
    acquisition = Story(id="2", title="Microsoft closes its deal for a game studio", url="u2", source="s")
    assert excluded(deals, cfg)
    assert not excluded(acquisition, cfg)


def test_rank_clusters_and_boosts_widely_covered_story(cfg):
    ranked = rank(load(cfg), cfg, now=NOW)
    top = ranked[0]
    assert "Chipmaker" in top.title
    assert top.also_in == ["Sample Feed A"]  # represented by the report with the full text
    assert all("deals" not in s.title for s in ranked)
    assert all("Old news" not in s.title for s in ranked)


def test_history_skips_covered_story(cfg):
    stories = load(cfg)
    chip = next(s for s in stories if s.url == "https://example.org/b/chip")
    history.add(cfg, chip, "job-1")
    ranked = rank(stories, cfg, now=NOW)
    assert all("Chipmaker" not in s.title for s in ranked)
    assert history.is_repeat(chip, history.recent(cfg))


def test_cluster_keeps_unrelated_apart(cfg):
    groups = cluster(load(cfg))
    assert len(groups) == 4  # chip story merged, deals, old, satellite


def test_helpers():
    assert site_name("https://www.theverge.com/2026/x") == "The Verge"
    assert site_name("https://blog.example.co/post") == "example.co"
    assert html_to_text("<p>Hi &amp; <b>bye</b></p>") == "Hi & bye"
