"""Tests for publishing scraped reviews to the INOUT website cache."""

from modules.neon_reviews import build_reviews_block
from modules.review_db import ReviewDB


def _make_review(
    review_id,
    *,
    text,
    rating=5,
    likes=0,
    date="3 weeks ago",
    review_date="2026-07-01",
    author="Reviewer",
):
    return {
        "review_id": review_id,
        "text": text,
        "rating": rating,
        "likes": likes,
        "lang": "en",
        "date": date,
        "review_date": review_date,
        "author": author,
        "profile": f"https://maps.google.com/profile/{review_id}",
        "avatar": f"https://lh3.googleusercontent.com/{review_id}",
        "owner_text": "",
        "photos": [],
    }


def test_build_reviews_block_matches_website_shape(tmp_path):
    db = ReviewDB(str(tmp_path / "reviews.db"))
    try:
        db.upsert_place(
            "inoutspaces",
            "INOUTSPACE",
            "https://maps.app.goo.gl/inout",
            resolved_url="https://www.google.com/maps/place/INOUTSPACE",
        )
        db.upsert_review(
            "inoutspaces",
            _make_review(
                "r1",
                text="Beautifully made furniture and patient consultation.",
                rating=5,
                likes=7,
                author="Asha",
            ),
        )
        db.upsert_review(
            "inoutspaces",
            _make_review("r2", text="Not a top review.", rating=3),
        )

        block = build_reviews_block(db, "inoutspaces", limit=5, min_rating=4)

        assert block["fromGoogle"] is True
        assert block["rating"] == 4.0
        assert block["count"] == 2
        assert block["mapsUri"] == "https://www.google.com/maps/place/INOUTSPACE"
        assert block["reviews"] == [
            {
                "q": "Beautifully made furniture and patient consultation.",
                "by": "Asha",
                "role": "3 weeks ago",
                "rating": 5,
                "photo": "https://lh3.googleusercontent.com/r1",
                "href": "https://maps.google.com/profile/r1",
            }
        ]
    finally:
        db.close()
