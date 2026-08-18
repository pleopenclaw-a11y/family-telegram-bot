from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import load_settings
from ninearm_client import NineArmClient

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "family_system.md"
EXTRACTION_SYSTEM = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8") + "\nYou are now operating in extraction mode. Return JSON only."


@dataclass(frozen=True)
class Extraction:
    action: str
    kind: str
    normalized_text: str
    confidence: float
    question: str = ""


def _json_from_response(result: dict[str, Any]) -> dict[str, Any]:
    content = result["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


def extract_message(client: NineArmClient, text: str) -> Extraction:
    prompt = """You classify a family Telegram message for shared memory.
Return JSON only, with exactly these keys:
{"action":"save|ignore|confirm", "kind":"event|expense|task|note", "normalized_text":"...", "confidence":0.0, "question":"..."}
Rules:
- save only useful family information: appointments, dates, places, expenses, tasks, reminders, or durable notes.
- ignore greetings, jokes, casual conversation, and empty messages.
- confirm when useful but missing an important date, amount, person, or meaning.
- normalized_text must be concise Thai, preserve facts, numbers, dates, and times.
- Do not invent missing facts.
Message: """ + text
    result = client.chat([
        {"role": "system", "content": EXTRACTION_SYSTEM},
        {"role": "user", "content": prompt},
    ])
    data = _json_from_response(result)
    action = data.get("action", "confirm")
    if action not in {"save", "ignore", "confirm"}:
        action = "confirm"
    kind = data.get("kind", "note")
    if kind not in {"event", "expense", "task", "note"}:
        kind = "note"
    return Extraction(action, kind, str(data.get("normalized_text", text)), float(data.get("confidence", 0)), str(data.get("question", "")))
