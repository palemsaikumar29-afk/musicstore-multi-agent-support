"""Shared test fixtures: seed an isolated DB per test session."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_DB = Path(__file__).parent / "test_musicstore.db"


@pytest.fixture(scope="session", autouse=True)
def _seed_test_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("ms") / "musicstore.db"
    os.environ["STORE_DB_PATH"] = str(db)
    # import after env is set so settings picks it up
    from src.database import db as dbmod

    dbmod.settings.store_db_path = str(db)
    dbmod.seed()
    yield
    os.environ.pop("STORE_DB_PATH", None)
