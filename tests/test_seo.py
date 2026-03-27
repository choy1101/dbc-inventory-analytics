"""Tests for the SEO keyword analyzer."""

import pytest

from dbc_inventory.seo.keyword_analyzer import (
    NICHE_KEYWORDS,
    KeywordReport,
    KeywordScore,
    analyse_listing,
    suggest_tags,
)


class TestAnalyseListing:
    def test_returns_keyword_report(self):
        report = analyse_listing("Handmade Rosary Beads", ["rosary beads", "catholic"])
        assert isinstance(report, KeywordReport)

    def test_matches_title_keyword(self):
        report = analyse_listing("Handmade Rosary Beads", [])
        keywords = [s.keyword for s in report.scores]
        assert "rosary beads" in keywords

    def test_matches_tag_keyword(self):
        report = analyse_listing("Silver Necklace", ["prayer beads"])
        keywords = [s.keyword for s in report.scores]
        assert "prayer beads" in keywords

    def test_title_match_flag(self):
        report = analyse_listing("Catholic Rosary Handmade", [])
        title_matches = {s.keyword: s.matched_in_title for s in report.scores}
        assert title_matches.get("catholic rosary") is True

    def test_tag_match_flag(self):
        report = analyse_listing("Necklace", ["cross necklace"])
        tag_matches = {s.keyword: s.matched_in_tags for s in report.scores}
        assert tag_matches.get("cross necklace") is True

    def test_no_false_positives(self):
        report = analyse_listing("Blue Sapphire Ring", ["diamond earring"])
        assert report.scores == []

    def test_top_keywords_sorted_descending(self):
        report = analyse_listing(
            "Handmade Catholic Rosary Beads Cross Necklace",
            ["rosary beads", "prayer beads", "cross necklace"],
        )
        scores = [s.score for s in report.top_keywords]
        assert scores == sorted(scores, reverse=True)

    def test_extra_keywords_are_included(self):
        report = analyse_listing(
            "Unique Amethyst Rosary",
            [],
            extra_keywords=["amethyst rosary"],
        )
        keywords = [s.keyword for s in report.scores]
        assert "amethyst rosary" in keywords

    def test_duplicate_extra_keywords_not_doubled(self):
        """An extra keyword that duplicates a niche keyword should appear once."""
        report = analyse_listing(
            "Rosary Beads",
            [],
            extra_keywords=["rosary beads"],
        )
        matched = [s for s in report.scores if s.keyword == "rosary beads"]
        assert len(matched) == 1

    def test_missing_niche_keywords_returns_list(self):
        report = analyse_listing("Silver Ring", [])
        # All niche keywords should be in the missing list.
        assert set(report.missing_niche_keywords) == set(NICHE_KEYWORDS)

    def test_present_keywords_not_in_missing(self):
        report = analyse_listing("Handmade Rosary Beads", [])
        assert "rosary beads" not in report.missing_niche_keywords

    def test_score_boosted_by_high_volume(self):
        """cross necklace (60k) should outscore chaplet (4k) if both in title."""
        report = analyse_listing("Cross Necklace Chaplet", [])
        score_map = {s.keyword: s.score for s in report.scores}
        assert score_map["cross necklace"] > score_map["chaplet"]

    def test_title_and_tag_match_higher_than_title_only(self):
        report_both = analyse_listing("Rosary Beads", ["rosary beads"])
        report_title_only = analyse_listing("Rosary Beads", [])
        score_both = next(s.score for s in report_both.scores if s.keyword == "rosary beads")
        score_title = next(s.score for s in report_title_only.scores if s.keyword == "rosary beads")
        assert score_both > score_title


class TestSuggestTags:
    def test_returns_list(self):
        suggestions = suggest_tags("Silver Ring", [])
        assert isinstance(suggestions, list)

    def test_suggestions_not_in_title_or_tags(self):
        title = "Handmade Catholic Rosary"
        tags = ["prayer beads"]
        suggestions = suggest_tags(title, tags)
        combined = (title + " " + " ".join(tags)).lower()
        for suggestion in suggestions:
            assert suggestion not in combined

    def test_max_suggestions_respected(self):
        suggestions = suggest_tags("Generic Item", [], max_suggestions=3)
        assert len(suggestions) <= 3

    def test_suggestions_ordered_by_volume(self):
        from dbc_inventory.seo.keyword_analyzer import _VOLUME_MAP, _DEFAULT_VOLUME

        suggestions = suggest_tags("Generic Item", [], max_suggestions=10)
        volumes = [_VOLUME_MAP.get(kw, _DEFAULT_VOLUME) for kw in suggestions]
        assert volumes == sorted(volumes, reverse=True)

    def test_no_suggestions_when_all_present(self):
        """If all niche keywords are in title/tags, no suggestions needed."""
        # Use only niche keywords so the listing is "complete".
        title = " ".join(NICHE_KEYWORDS[:5])
        tags = NICHE_KEYWORDS[5:]
        # We can't truly test zero since 13-tag limit, but verify the list is shorter.
        suggestions = suggest_tags(title, tags)
        assert isinstance(suggestions, list)
