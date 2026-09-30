"""SQLite music-store database: schema + deterministic seed data.

Run: python -m src.database.db --seed
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from ..services.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS artists (
    artist_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS genres (
    genre_id    INTEGER PRIMARY KEY,
    name        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS albums (
    album_id    INTEGER PRIMARY KEY,
    artist_id   INTEGER NOT NULL REFERENCES artists(artist_id),
    title       TEXT NOT NULL,
    price_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tracks (
    track_id    INTEGER PRIMARY KEY,
    album_id    INTEGER NOT NULL REFERENCES albums(album_id),
    title       TEXT NOT NULL,
    genre_id    INTEGER NOT NULL REFERENCES genres(genre_id),
    duration_ms INTEGER NOT NULL,
    price_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id    INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    invoice_date  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'delivered',
    total_cents   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS invoice_lines (
    line_id     INTEGER PRIMARY KEY,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(invoice_id),
    track_id    INTEGER NOT NULL REFERENCES tracks(track_id),
    unit_price_cents INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album_id);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_lines_invoice ON invoice_lines(invoice_id);
"""

SEED_ARTISTS = [
    (1, "The Midnight Circuits"),
    (2, "Aurora Fields"),
    (3, "Copper & Static"),
    (4, "DJ Meridian"),
    (5, "Willow Hart"),
    (6, "The Brass Lanterns"),
    (7, "Neon Pilgrim"),
    (8, "Saffron Sky"),
]

SEED_GENRES = [(1, "Rock"), (2, "Pop"), (3, "Jazz"), (4, "Electronic"), (5, "Folk")]

SEED_ALBUMS = [
    (1, 1, "Neon Highways", 999),
    (2, 1, "Voltage Dreams", 899),
    (3, 2, "Northern Lights", 1099),
    (4, 3, "Rust Belt Ballads", 799),
    (5, 4, "Bass Cathedral", 949),
    (6, 5, "Paper Moons", 849),
    (7, 6, "Second Line", 999),
    (8, 7, "Synth Pilgrimage", 1049),
    (9, 8, "Monsoon Letters", 899),
    (10, 2, "Glacier Hymns", 999),
]

# (track_id, album_id, title, genre_id, duration_ms, price_cents)
SEED_TRACKS = [
    (1, 1, "Neon Highways", 1, 214000, 129),
    (2, 1, "Midnight Overdrive", 1, 198000, 129),
    (3, 1, "Glass Thunder", 1, 243000, 129),
    (4, 2, "Voltage Dreams", 4, 187000, 129),
    (5, 2, "Circuit Bloom", 4, 221000, 129),
    (6, 2, "Static Lullaby", 4, 176000, 129),
    (7, 3, "Northern Lights", 2, 205000, 129),
    (8, 3, "Fjord Song", 5, 232000, 129),
    (9, 3, "Aurora Rising", 2, 189000, 129),
    (10, 4, "Rust Belt Ballads", 1, 254000, 129),
    (11, 4, "Factory Smoke", 1, 218000, 129),
    (12, 4, "Copper Sunrise", 1, 201000, 129),
    (13, 5, "Bass Cathedral", 4, 312000, 129),
    (14, 5, "Meridian Pulse", 4, 245000, 129),
    (15, 5, "Night Transit", 4, 278000, 129),
    (16, 6, "Paper Moons", 5, 196000, 129),
    (17, 6, "Willow Creek", 5, 223000, 129),
    (18, 6, "September Thread", 5, 187000, 129),
    (19, 7, "Second Line", 3, 234000, 129),
    (20, 7, "Brass Parade", 3, 212000, 129),
    (21, 7, "Lantern Waltz", 3, 198000, 129),
    (22, 8, "Synth Pilgrimage", 4, 265000, 129),
    (23, 8, "Neon Pilgrim Anthem", 4, 241000, 129),
    (24, 8, "Digital Horizon", 4, 219000, 129),
    (25, 9, "Monsoon Letters", 5, 208000, 129),
    (26, 9, "Saffron Rain", 5, 195000, 129),
    (27, 9, "River Delta Blues", 1, 226000, 129),
    (28, 10, "Glacier Hymns", 2, 242000, 129),
    (29, 10, "Icefield Choir", 2, 216000, 129),
    (30, 10, "Whiteout", 1, 188000, 129),
    (31, 1, "Downtown Afterglow", 1, 205000, 129),
    (32, 3, "Tundra Drive", 2, 197000, 129),
    (33, 5, "Warehouse Hymn", 4, 289000, 129),
    (34, 6, "Harvest Moonrise", 5, 211000, 129),
    (35, 7, "Crescent Street", 3, 224000, 129),
    (36, 9, "Desert Postcard", 5, 200000, 129),
]

SEED_CUSTOMERS = [
    (1, "Priya", "Nair", "priya.nair@example.com"),
    (2, "Marcus", "Bell", "marcus.bell@example.com"),
    (3, "Elena", "Vargas", "elena.vargas@example.com"),
    (4, "Tom", "Okafor", "tom.okafor@example.com"),
    (5, "Jia", "Chen", "jia.chen@example.com"),
]

# (invoice_id, customer_id, date, status, total_cents, [track_ids])
SEED_INVOICES = [
    (1001, 1, "2026-08-02", "delivered", 387, [1, 2, 3]),
    (1002, 1, "2026-09-10", "shipped", 258, [7, 9]),
    (1003, 2, "2026-07-19", "delivered", 516, [13, 14, 15, 33]),
    (1004, 3, "2026-09-25", "processing", 129, [25]),
    (1005, 3, "2026-06-30", "delivered", 774, [19, 20, 21, 35, 34, 16]),
    (1006, 4, "2026-09-28", "shipped", 387, [27, 36, 12]),
    (1007, 5, "2026-08-15", "delivered", 258, [22, 23]),
]


def db_path() -> Path:
    p = Path(settings.store_db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_conn(db: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db or db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed(force: bool = True) -> Path:
    path = db_path()
    if force and path.exists():
        path.unlink()
    conn = get_conn(path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO artists VALUES (?, ?)", SEED_ARTISTS)
        conn.executemany("INSERT INTO genres VALUES (?, ?)", SEED_GENRES)
        conn.executemany("INSERT INTO albums VALUES (?, ?, ?, ?)", SEED_ALBUMS)
        conn.executemany("INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?)", SEED_TRACKS)
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", SEED_CUSTOMERS)
        track_price = {t[0]: t[5] for t in SEED_TRACKS}
        for inv_id, cust_id, date, status, total, track_ids in SEED_INVOICES:
            conn.execute(
                "INSERT INTO invoices VALUES (?, ?, ?, ?, ?)",
                (inv_id, cust_id, date, status, total),
            )
            for tid in track_ids:
                conn.execute(
                    "INSERT INTO invoice_lines (invoice_id, track_id, unit_price_cents)"
                    " VALUES (?, ?, ?)",
                    (inv_id, tid, track_price[tid]),
                )
        conn.commit()
    finally:
        conn.close()
    return path


def ensure_seeded() -> Path:
    path = db_path()
    if not path.exists() or path.stat().st_size == 0:
        return seed()
    conn = get_conn(path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    except sqlite3.Error:
        conn.close()
        return seed()
    conn.close()
    return seed() if n == 0 else path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    args = parser.parse_args()
    if args.seed:
        print(f"seeded {seed()}")
    else:
        print(f"db at {db_path()}")
