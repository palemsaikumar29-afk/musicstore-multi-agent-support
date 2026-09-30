"""Catalog read-model: search tracks/albums/artists, recommendations."""
from __future__ import annotations

from ..database.db import get_conn


def _row_to_track(row) -> dict:
    return {
        "track_id": row["track_id"],
        "title": row["title"],
        "artist": row["artist"],
        "album": row["album"],
        "genre": row["genre"],
        "duration_s": row["duration_ms"] // 1000,
        "price": f"${row['price_cents'] / 100:.2f}",
    }


def search_tracks(query: str, limit: int = 8) -> list[dict]:
    q = f"%{query.strip().lower()}%"
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT t.track_id, t.title, a.name AS artist, al.title AS album,
                      g.name AS genre, t.duration_ms, t.price_cents
               FROM tracks t
               JOIN albums al ON al.album_id = t.album_id
               JOIN artists a ON a.artist_id = al.artist_id
               JOIN genres g ON g.genre_id = t.genre_id
               WHERE lower(t.title) LIKE ? OR lower(a.name) LIKE ?
                     OR lower(al.title) LIKE ? OR lower(g.name) LIKE ?
               ORDER BY t.title LIMIT ?""",
            (q, q, q, q, limit),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_track(r) for r in rows]


def list_albums(limit: int = 12) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT al.title, a.name AS artist, al.price_cents,
                      COUNT(t.track_id) AS tracks
               FROM albums al
               JOIN artists a ON a.artist_id = al.artist_id
               LEFT JOIN tracks t ON t.album_id = al.album_id
               GROUP BY al.album_id ORDER BY al.title LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "album": r["title"],
            "artist": r["artist"],
            "tracks": r["tracks"],
            "price": f"${r['price_cents'] / 100:.2f}",
        }
        for r in rows
    ]


def recommend_for_track(track_id: int, limit: int = 5) -> list[dict]:
    """Recommend tracks from the same genre, excluding the track itself."""
    conn = get_conn()
    try:
        genre = conn.execute(
            "SELECT genre_id FROM tracks WHERE track_id = ?", (track_id,)
        ).fetchone()
        if genre is None:
            return []
        rows = conn.execute(
            """SELECT t.track_id, t.title, a.name AS artist, al.title AS album,
                      g.name AS genre, t.duration_ms, t.price_cents
               FROM tracks t
               JOIN albums al ON al.album_id = t.album_id
               JOIN artists a ON a.artist_id = al.artist_id
               JOIN genres g ON g.genre_id = t.genre_id
               WHERE t.genre_id = ? AND t.track_id != ?
               ORDER BY t.title LIMIT ?""",
            (genre["genre_id"], track_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_track(r) for r in rows]


def recommend_for_artist(artist_name: str, limit: int = 5) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT t.track_id, t.title, a.name AS artist, al.title AS album,
                      g.name AS genre, t.duration_ms, t.price_cents
               FROM tracks t
               JOIN albums al ON al.album_id = t.album_id
               JOIN artists a ON a.artist_id = al.artist_id
               JOIN genres g ON g.genre_id = t.genre_id
               WHERE lower(a.name) = lower(?)
               ORDER BY t.title LIMIT ?""",
            (artist_name.strip(), limit),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_track(r) for r in rows]
