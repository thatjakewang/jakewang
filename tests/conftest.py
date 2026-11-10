"""Settings have no defaults for these two, so give the import something to
read. Nothing here connects: the engine is lazy and the tests never query."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@127.0.0.1:1/test")
os.environ.setdefault("SHORTCUT_API_KEY", "test-key")
