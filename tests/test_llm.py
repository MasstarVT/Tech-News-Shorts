import json

import httpx
import pytest

from technews.config import AppConfig
from technews.llm import complete, route_for
from technews.llm.base import LLMError
from technews.script.schema import draft_model

DRAFT = {
    "title": "T", "topic": "AI",
    "scenes": [{"narration": "Hello there.", "visual": {"type": "headline", "text": "Hi", "value": "", "label": "",
                                                        "trend": "none", "icon": "", "left": "", "right": "", "items": []}}],
    "outro": "Bye.", "description": "D", "hashtags": ["ai"],
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=httpx.Request("POST", "http://x"), response=httpx.Response(self.status_code))


def test_ollama_structured_output(monkeypatch, cfg: AppConfig):
    sent = {}

    def fake_post(url, json=None, timeout=None):  # noqa: A002
        sent.update(url=url, body=json)
        return FakeResponse({"message": {"content": __import__("json").dumps(DRAFT)}, "prompt_eval_count": 10, "eval_count": 5})

    monkeypatch.setattr(httpx, "post", fake_post)
    route = route_for("script", cfg)
    res = complete("script", "system", "user", draft_model(), route=route, cfg=cfg)
    assert res.data.title == "T"
    assert res.provider == "ollama" and res.model == "qwen3:14b"
    assert sent["url"].endswith("/api/chat")
    assert sent["body"]["format"]["type"] == "object"
    assert "think" not in sent["body"]  # only sent when an effort is configured
    # cached on the second call
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("should be cached"))
    assert complete("script", "system", "user", draft_model(), route=route, cfg=cfg).cached


def test_invalid_json_is_retried_then_fails(monkeypatch, cfg: AppConfig):
    calls = []

    def fake_post(url, json=None, timeout=None):  # noqa: A002
        calls.append(json)
        return FakeResponse({"message": {"content": "not json"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LLMError):
        complete("script", "s", "u", draft_model(), route=route_for("script", cfg), cfg=cfg, use_cache=False)
    assert len(calls) == 3
    assert "previous answer was not valid" in calls[-1]["messages"][1]["content"]


def test_route_override(cfg: AppConfig):
    assert route_for("script", cfg, "null").provider == "null"
    r = route_for("script", cfg, "ollama:llama3.1:8b")
    assert (r.provider, r.model) == ("ollama", "llama3.1:8b")
    assert json.dumps(r.model_dump())
