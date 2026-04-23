import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Use a fresh temporary SQLite database for every test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_PATH", path)

    # Reload the db module so it picks up the new DATABASE_PATH
    import importlib
    from app.database import db as db_module

    importlib.reload(db_module)
    db_module.init_db()

    yield path

    os.unlink(path)
