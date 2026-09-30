from src.database import db as dbmod
from src.services import catalog, orders


def test_seed_counts():
    conn = dbmod.get_conn()
    try:
        assert conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0] == 8
        assert conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0] == 10
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 36
        assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 5
        assert conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 7
    finally:
        conn.close()


def test_search_tracks_by_title():
    hits = catalog.search_tracks("Neon")
    assert len(hits) >= 3
    titles = {h["title"] for h in hits}
    assert "Neon Highways" in titles


def test_search_tracks_by_genre():
    hits = catalog.search_tracks("jazz")
    assert len(hits) >= 3
    assert all(h["genre"] == "Jazz" for h in hits)


def test_search_tracks_by_artist():
    hits = catalog.search_tracks("DJ Meridian")
    assert hits and all(h["artist"] == "DJ Meridian" for h in hits)


def test_search_no_results():
    assert catalog.search_tracks("zzz-no-such-track") == []


def test_list_albums():
    albums = catalog.list_albums()
    assert len(albums) == 10
    assert all("album" in a and "price" in a for a in albums)


def test_recommend_for_track_same_genre():
    recs = catalog.recommend_for_track(1, 3)
    assert recs and all(r["genre"] == "Rock" for r in recs)
    assert all(r["track_id"] != 1 for r in recs)


def test_recommend_unknown_track():
    assert catalog.recommend_for_track(999999) == []


def test_recommend_for_artist():
    recs = catalog.recommend_for_artist("Willow Hart")
    assert recs and all(r["artist"] == "Willow Hart" for r in recs)


def test_orders_for_email():
    found = orders.orders_for_email("priya.nair@example.com")
    assert len(found) == 2
    assert found[0]["invoice_id"] == 1002  # newest first


def test_orders_for_unknown_email():
    assert orders.orders_for_email("nobody@example.com") == []


def test_order_detail():
    d = orders.order_detail(1001)
    assert d is not None
    assert d["status"] == "delivered"
    assert len(d["items"]) == 3


def test_order_detail_unknown():
    assert orders.order_detail(424242) is None


def test_policy_answers():
    for topic in ("returns", "delivery", "payments", "account"):
        assert len(orders.policy_answer(topic)) > 20
    assert "human agent" in orders.policy_answer("nope")
