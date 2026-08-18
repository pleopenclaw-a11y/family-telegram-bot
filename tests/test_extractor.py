import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from extractor import extract_message


def test_extractor_preserves_shopping_kind():
    class FakeClient:
        def chat(self, messages):
            return {
                "choices": [{"message": {"content": (
                    '{"action":"save","kind":"shopping",'
                    '"normalized_text":"นม 2 ลิตร","confidence":0.9,"question":""}'
                )}}]
            }

    result = extract_message(FakeClient(), "ซื้อนม 2 ลิตร")

    assert result.kind == "shopping"
