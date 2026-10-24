"""Shared test setup. Runs before any test module imports the app.

Tests must not depend on whoever's local .env: load_dotenv() never overrides variables that are
already set, so pinning them here keeps a real API_SHARED_KEY (tunnel guard) or API keys in .env
from turning every request into a 401 or a real paid call.
"""
import os

os.environ["API_SHARED_KEY"] = ""   # tests that need the guard set it with monkeypatch
os.environ["MOCK_AI"] = "1"
