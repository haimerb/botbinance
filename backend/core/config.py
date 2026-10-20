import os
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.services.bot_runner import BotRunner

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000"
).split(",")

limiter = Limiter(key_func=get_remote_address)

bot = BotRunner(mock_mode=MOCK_MODE, dry_run=DRY_RUN)
