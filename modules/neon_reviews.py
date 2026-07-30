"""
Publish scraped Google reviews to the INOUT website's Neon settings table.

The website reads `settings.key = 'googleReviews'` as a JSONB ReviewsBlock.
This module intentionally depends on the local SQLite ReviewDB for scraping
state and only uses Neon as the public website cache.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from modules.review_db import ReviewDB


DEFAULT_SETTINGS_KEY = "googleReviews"


def _load_dotenv_value(name: str, dotenv_path: str = ".env") -> Optional[str]:
    """Read a single KEY=value from a local .env file without extra deps."""
    path = Path(dotenv_path)
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return None


def _first_text(value: Any) -> str:
    """Return a useful text value from multilingual review fields."""
    if isinstance(value, dict):
        if value.get("en"):
            return str(value["en"]).strip()
        for item in value.values():
            if isinstance(item, str) and item.strip():
                return item.strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _as_int_rating(value: Any) -> Optional[int]:
    try:
        rating = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if 1 <= rating <= 5:
        return rating
    return None


def _sort_reviews(reviews: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return sorted(
        reviews,
        key=lambda r: (
            float(r.get("rating") or 0),
            int(r.get("likes") or 0),
            r.get("review_date") or "",
            r.get("created_date") or "",
        ),
        reverse=True,
    )


def build_reviews_block(
    db: ReviewDB,
    place_id: str,
    *,
    limit: int = 5,
    min_rating: int = 4,
) -> Dict[str, Any]:
    """Build the website ReviewsBlock from local scraped reviews."""
    place = db.get_place(place_id)
    if not place:
        raise ValueError(f"Place not found in local SQLite database: {place_id}")

    rows = db.get_reviews(place_id, include_deleted=False)
    candidates = []
    for row in rows:
        text = _first_text(row.get("review_text"))
        rating = _as_int_rating(row.get("rating"))
        if not text or rating is None or rating < min_rating:
            continue
        candidates.append(
            {
                "q": text,
                "by": row.get("author") or "Google reviewer",
                "role": row.get("raw_date") or row.get("review_date") or "",
                "rating": rating,
                "photo": row.get("profile_picture") or None,
                "href": row.get("profile_url") or None,
                "_sort": row,
            }
        )

    reviews = []
    for item in _sort_reviews(candidates)[:limit]:
        public_item = {k: v for k, v in item.items() if k != "_sort" and v}
        reviews.append(public_item)

    ratings = [
        float(row.get("rating"))
        for row in rows
        if row.get("rating") not in (None, "", 0)
    ]
    average_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
    maps_uri = place.get("resolved_url") or place.get("original_url") or None

    block: Dict[str, Any] = {
        "reviews": reviews,
        "fromGoogle": True,
        "count": int(place.get("total_reviews") or len(rows)),
    }
    if average_rating is not None:
        block["rating"] = average_rating
    if maps_uri:
        block["mapsUri"] = maps_uri
    return block


def publish_reviews_block(
    block: Dict[str, Any],
    *,
    database_url: Optional[str] = None,
    settings_key: str = DEFAULT_SETTINGS_KEY,
) -> None:
    """Upsert ReviewsBlock JSON into the website Neon settings table."""
    url = (
        database_url
        or os.getenv("DATABASE_URL")
        or os.getenv("NEON_DATABASE_URL")
        or _load_dotenv_value("DATABASE_URL")
        or _load_dotenv_value("NEON_DATABASE_URL")
    )
    if not url:
        raise ValueError(
            "Missing Neon connection string. Set DATABASE_URL/NEON_DATABASE_URL "
            "or pass --database-url."
        )

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'psycopg'. Install requirements.txt before publishing."
        ) from exc

    payload = json.dumps(block, ensure_ascii=False)
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL
                )
                """
            )
            cur.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (settings_key, payload),
            )
        conn.commit()
