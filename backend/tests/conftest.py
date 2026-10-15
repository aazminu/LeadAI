import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("NEWS_API_KEY", "test-key")
os.environ.setdefault("CENSUS_API_KEY", "test-key")
os.environ.setdefault("FRED_API_KEY", "test-key")
os.environ.setdefault("WALKSCORE_API_KEY", "test-key")
os.environ.setdefault("ADZUNA_APP_ID", "test-id")
os.environ.setdefault("ADZUNA_APP_KEY", "test-key")

