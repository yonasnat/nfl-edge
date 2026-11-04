"""Load settings from .env.local or .env when running on your own computer.

`neon deploy` / `neon env pull` write DATABASE_URL (pooled) and DATABASE_URL_UNPOOLED (direct)
into one of these files. Real environment variables (like the ones set in Render) always win.
"""
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

for name in (".env.local", ".env"):
    if (ROOT / name).exists():
        load_dotenv(ROOT / name, override=False)
