"""Shared test setup. Runs before any test module imports the app.

Tests must not depend on whoever's local .env: load_dotenv() never overrides variables that are
already set, so pinning them here keeps a real API_SHARED_KEY (tunnel guard), PUBLIC_BASE (tunnel
URL) or API keys in .env from turning requests into 401s, wrong URLs, or real paid calls.
Tests that need one of these set it themselves with monkeypatch.
"""
import os

os.environ["API_SHARED_KEY"] = ""
os.environ["MOCK_AI"] = "1"
os.environ["PUBLIC_BASE"] = "http://localhost:8000"
for _key in ("APIFY_TOKEN", "NESSIE_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
             "MOSS_PROJECT_ID", "MOSS_PROJECT_KEY"):
    os.environ[_key] = ""
