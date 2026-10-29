import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Support Render Secret Files, local .env, and plain Environment Variables
for p in (Path("/etc/secrets/.env"), Path(".env")):
    if p.exists():
        load_dotenv(p)
        break
else:
    load_dotenv()


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable; ignore template placeholders."""
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = _env_int("ADMIN_ID", 8995385837)
    TEST_MODE: bool = os.getenv("TEST_MODE", "true").lower() in ("true", "1", "yes")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot.db")
    ROLLYPAY_API_KEY: str = os.getenv("ROLLYPAY_API_KEY", "")
    ROLLYPAY_TERMINAL_ID: str = os.getenv("ROLLYPAY_TERMINAL_ID", "")
    ROLLYPAY_SIGNING_SECRET: str = os.getenv("ROLLYPAY_SIGNING_SECRET", "")
    ROLLYPAY_API_BASE: str = os.getenv("ROLLYPAY_API_BASE", "https://api.rollypay.io").rstrip("/")
    ROLLYPAY_CALLBACK_PATH: str = os.getenv("ROLLYPAY_CALLBACK_PATH", "/payments/callback")
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    PORT: int = _env_int("PORT", 8080)
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "").lstrip("@")
    H1CLOUD_API_BASE: str = os.getenv("H1CLOUD_API_BASE", "https://s-25154.pl7.h1clayd.click/api").rstrip("/")
    H1CLOUD_API_TOKEN: str = os.getenv("H1CLOUD_API_TOKEN", "")
    H1CLOUD_DEVICE_LIMIT: int = _env_int("H1CLOUD_DEVICE_LIMIT", 3)
    H1CLOUD_TRAFFIC_LIMIT_GB: float = float(os.getenv("H1CLOUD_TRAFFIC_LIMIT_GB", "0"))
    PRIVACY_POLICY_URL: str = "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-08-12-99"
    TERMS_URL: str = "https://telegra.ph/PUBLICHNAYA-OFERTA-08-12-15"


config = Config()
if not config.BOT_TOKEN or config.BOT_TOKEN in ("PASTE_TELEGRAM_BOT_TOKEN_HERE", "PASTE_NEW_TOKEN_FROM_BOTFATHER"):
    raise ValueError("Укажите новый BOT_TOKEN в переменных окружения/.env")
