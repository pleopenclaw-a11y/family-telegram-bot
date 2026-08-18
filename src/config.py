from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    ninearm_base_url: str
    ninearm_api_key: str
    primary_model: str
    fallback_model: str
    embedding_model: str
    family_board_api_token: str
    family_board_allowed_origin: str

def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        ninearm_base_url=os.getenv("NINEARM_BASE_URL", "https://gateway.9arm.co/v1"),
        ninearm_api_key=os.getenv("NINEARM_API_KEY", ""),
        primary_model=os.getenv("NINEARM_PRIMARY_MODEL", "deepseek-v4-flash-0731"),
        fallback_model=os.getenv("NINEARM_FALLBACK_MODEL", "qwen3.8-27b-fp8"),
        embedding_model=os.getenv("NINEARM_EMBEDDING_MODEL", ""),
        family_board_api_token=os.getenv("FAMILY_BOARD_API_TOKEN", ""),
        family_board_allowed_origin=os.getenv("FAMILY_BOARD_ALLOWED_ORIGIN", ""),
    )
