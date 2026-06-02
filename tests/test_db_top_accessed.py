from torsor_helper import db


def test_top_accessed_orders_by_count_excludes_zero(tmp_path):
    conn = db.connect(tmp_path / "torsor.db")
    for path in ("a.md", "b.md", "c.md"):
        db.upsert_note(conn, path, "h", 4, "journal", None, path, "t")
    db.bump_access(conn, ["a.md", "a.md", "a.md"])  # a -> 3
    db.bump_access(conn, ["b.md"])                   # b -> 1
    top = db.top_accessed(conn, limit=5)
    assert top[0] == ("a.md", 3)
    assert ("b.md", 1) in top
    assert all(p != "c.md" for p, _ in top)
