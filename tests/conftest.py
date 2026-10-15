"""Test environment. Runs before any test module (and before the app config is imported)."""
import os

# Always use dummy secrets in tests: a real bot token must never be reachable from the test run.
os.environ["BOT_TOKEN"] = "123456:TEST_TOKEN_NOT_REAL"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-that-is-at-least-32-chars-long"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

# When a real PostgreSQL is supplied, the app itself (engine, session maker) talks to it too.
if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
