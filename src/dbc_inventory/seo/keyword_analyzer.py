"""SEO keyword analyzer for religious-jewellery listings.

Analyses keyword relevance and estimated search volume for Etsy listings
in the Rosary / religious-jewellery niche, helping DivineBeadCraft surface
high-performing tags and titles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

# ---------------------------------------------------------------------------
# Seed data – curated for the DivineBeadCraft niche (2026)
# ---------------------------------------------------------------------------

#: Base keywords that are highly relevant to the shop's niche.
NICHE_KEYWORDS: list[str] = [
    "rosary beads",
    "catholic rosary",
    "handmade rosary",
    "religious jewelry",
    "prayer beads",
    "cross necklace",
    "saint medal",
    "first communion gift",
    "confirmation gift",
    "baptism gift",
    "gemstone rosary",
    "crystal rosary",
    "custom rosary",
    "personalized rosary",
    "wedding rosary",
    "chaplet",
    "orthodox prayer rope",
    "divine mercy chaplet",
    "our lady of guadalupe",
    "miraculous medal",
    "crucifix necklace",
    "patron saint necklace",
    "religious bracelet",
    "holy spirit gift",
    "catholic gift",
]

#: Multipliers applied when a keyword appears in a listing title vs. a tag.
_TITLE_WEIGHT = 1.5
_TAG_WEIGHT = 1.0

#: Rough estimated-search-volume buckets (searches/month on Etsy).
_VOLUME_MAP: dict[str, int] = {
    "rosary beads": 45_000,
    "catholic rosary": 30_000,
    "handmade rosary": 12_000,
    "religious jewelry": 20_000,
    "prayer beads": 18_000,
    "cross necklace": 60_000,
    "saint medal": 8_000,
    "first communion gift": 22_000,
    "confirmation gift": 15_000,
    "baptism gift": 25_000,
    "gemstone rosary": 5_000,
    "crystal rosary": 7_500,
    "custom rosary": 9_000,
    "personalized rosary": 11_000,
    "wedding rosary": 6_000,
    "chaplet": 4_000,
    "orthodox prayer rope": 2_500,
    "divine mercy chaplet": 3_000,
    "our lady of guadalupe": 10_000,
    "miraculous medal": 8_500,
    "crucifix necklace": 14_000,
    "patron saint necklace": 6_500,
    "religious bracelet": 9_500,
    "holy spirit gift": 3_500,
    "catholic gift": 17_000,
}

_DEFAULT_VOLUME = 1_000


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(order=True, frozen=True)
class KeywordScore:
    """Relevance score and metadata for a single keyword."""

    score: float
    keyword: str
    estimated_monthly_searches: int
    matched_in_title: bool
    matched_in_tags: bool

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"{self.keyword!r:40s}  score={self.score:.2f}"
            f"  ~{self.estimated_monthly_searches:,} searches/mo"
        )


@dataclass
class KeywordReport:
    """Full SEO analysis report for a listing."""

    listing_title: str
    listing_tags: list[str]
    scores: list[KeywordScore] = field(default_factory=list)

    # ---------- derived properties ----------

    @property
    def top_keywords(self) -> list[KeywordScore]:
        """Return keywords sorted by descending score."""
        return sorted(self.scores, reverse=True)

    @property
    def missing_niche_keywords(self) -> list[str]:
        """Niche keywords absent from both title and tags."""
        matched = {s.keyword for s in self.scores if s.matched_in_title or s.matched_in_tags}
        return [kw for kw in NICHE_KEYWORDS if kw not in matched]

    def summary(self) -> str:  # pragma: no cover
        lines = [
            f"=== SEO Report for: {self.listing_title!r} ===",
            "",
            "Top matching keywords:",
        ]
        for s in self.top_keywords[:10]:
            lines.append(f"  {s}")
        lines += [
            "",
            f"Missing niche keywords ({len(self.missing_niche_keywords)}):",
        ]
        for kw in self.missing_niche_keywords[:10]:
            lines.append(f"  - {kw}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core analyser
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for comparison."""
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).strip()


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Return True if *keyword* appears as a whole phrase inside *text*."""
    return keyword in _normalize(text)


def analyse_listing(
    title: str,
    tags: Iterable[str],
    *,
    extra_keywords: Iterable[str] | None = None,
) -> KeywordReport:
    """Analyse an Etsy listing and return a :class:`KeywordReport`.

    Parameters
    ----------
    title:
        The listing title text.
    tags:
        The listing tags (up to 13 on Etsy).
    extra_keywords:
        Additional keywords to evaluate beyond the built-in niche list.

    Returns
    -------
    KeywordReport
        Contains a :class:`KeywordScore` for every matching keyword and a
        list of missing niche keywords that could improve discoverability.
    """
    tag_list = list(tags)
    all_keywords = list(NICHE_KEYWORDS) + list(extra_keywords or [])

    norm_title = _normalize(title)
    norm_tags = [_normalize(t) for t in tag_list]
    joined_tags = " ".join(norm_tags)

    scores: list[KeywordScore] = []
    seen: set[str] = set()

    for kw in all_keywords:
        if kw in seen:
            continue
        seen.add(kw)

        in_title = _keyword_in_text(kw, norm_title)
        in_tags = _keyword_in_text(kw, joined_tags)

        if not in_title and not in_tags:
            continue

        volume = _VOLUME_MAP.get(kw, _DEFAULT_VOLUME)
        raw_score = 0.0
        if in_title:
            raw_score += _TITLE_WEIGHT
        if in_tags:
            raw_score += _TAG_WEIGHT

        # Boost by (log-scaled) search volume so high-traffic keywords rank higher.
        import math

        volume_boost = math.log10(max(volume, 1)) / 5  # normalised ~0-1
        final_score = round(raw_score * (1 + volume_boost), 4)

        scores.append(
            KeywordScore(
                score=final_score,
                keyword=kw,
                estimated_monthly_searches=volume,
                matched_in_title=in_title,
                matched_in_tags=in_tags,
            )
        )

    return KeywordReport(listing_title=title, listing_tags=tag_list, scores=scores)


def suggest_tags(
    title: str,
    current_tags: Iterable[str],
    *,
    max_suggestions: int = 5,
) -> list[str]:
    """Suggest additional Etsy tags that would improve SEO.

    Returns up to *max_suggestions* niche keywords not already present in
    *current_tags* or *title*, ordered by estimated monthly search volume.

    Parameters
    ----------
    title:
        Current listing title.
    current_tags:
        Tags already applied to the listing.
    max_suggestions:
        Maximum number of tag suggestions to return.
    """
    report = analyse_listing(title, current_tags)
    missing = report.missing_niche_keywords

    # Order missing keywords by estimated search volume (descending).
    scored_missing = sorted(
        missing,
        key=lambda kw: _VOLUME_MAP.get(kw, _DEFAULT_VOLUME),
        reverse=True,
    )
    return scored_missing[:max_suggestions]
