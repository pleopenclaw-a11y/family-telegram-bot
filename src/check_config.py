from config import load_settings

s = load_settings()
required = {
    "NINEARM_API_KEY": s.ninearm_api_key,
    "NINEARM_PRIMARY_MODEL": s.primary_model,
    "NINEARM_FALLBACK_MODEL": s.fallback_model,
}
missing = [name for name, value in required.items() if not value or value == "replace_with_rotated_key"]
if missing:
    raise SystemExit(f"Missing configuration: {', '.join(missing)}")

print({
    "base_url": s.ninearm_base_url,
    "primary_model": s.primary_model,
    "fallback_model": s.fallback_model,
    "embedding_model_configured": bool(s.embedding_model),
    "telegram_token_configured": bool(s.telegram_bot_token),
})
