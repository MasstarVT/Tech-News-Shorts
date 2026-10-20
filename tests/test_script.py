import json

from technews.script import fallback, prompts
from technews.script.normalize import build_script, unverified_numbers
from technews.script.schema import draft_model, icon_names


def scene(narration, **visual):
    base = {"type": "headline", "text": "", "value": "", "label": "", "trend": "none", "icon": "", "left": "",
            "right": "", "items": []}
    return {"narration": narration, "visual": {**base, **visual}}


def draft(scenes, **kw):
    return {"title": "A title", "topic": "Chips", "scenes": scenes, "outro": "What do you think?",
            "description": "Desc.", "hashtags": ["#tech", "Tech", "chips!"], **kw}


def test_first_scene_becomes_headline_with_topic_stamp(cfg, story):
    s = build_script(draft([scene("The chip is 30% faster.", type="stat", value="30%")]), story, cfg, "test")
    assert s.scenes[0].visual.type == "headline"
    assert s.scenes[0].visual.tag == "Chips"
    assert s.scenes[-1].visual.type == "outro"
    assert s.scenes[-1].narration == "What do you think?"
    assert s.hashtags == ["tech", "chips"]


def test_visual_repairs(cfg, story):
    s = build_script(draft([
        scene("Hook sentence here.", text="Faster chips"),
        scene("It is 30% faster.", type="stat", value="30%", label="speed gain", trend="up"),
        scene("It costs a lot.", type="stat", value="lots"),  # no number -> headline
        scene("Made up number.", type="stat", value="$9B", label="revenue"),  # not in article -> headline + warning
        scene("Icons.", type="icon", icon="not-an-icon", text="A label"),
        scene("Versus.", type="versus", left="Old", right=""),
    ]), story, cfg, "test")
    types = [x.visual.type for x in s.scenes]
    assert types[:6] == ["headline", "stat", "headline", "headline", "icon", "headline"]
    assert s.scenes[1].visual.trend == "up"
    assert s.scenes[4].visual.icon == "news"
    assert any("$9B" in w for w in s.warnings)


def test_stat_keeps_unit_marks(cfg, story):
    story.text += ' The screen measures 8.4" diagonally.'
    s = build_script(draft([scene("Hook."), scene("Screen size.", type="stat", value='8.4"', label="screen")]),
                     story, cfg, "test")
    assert s.scenes[1].visual.value == '8.4"'


def test_word_budget_trims_middle_scenes(cfg, story):
    long = " ".join(["word"] * 30) + "."
    s = build_script(draft([scene(long) for _ in range(6)]), story, cfg, "test")
    assert s.word_count <= cfg.script.max_words + 15
    assert len(s.scenes) >= cfg.script.min_scenes + 1


def test_unverified_numbers(story):
    assert unverified_numbers("It is 30% faster and costs $499", story.context) == []
    assert unverified_numbers("It sold 2,000,000 units", story.context) == ["2000000"]


def test_fallback_draft_is_valid(cfg, story):
    s = build_script(fallback.draft(story), story, cfg, "null")
    assert s.scenes[0].visual.type == "headline"
    assert len(s.scenes) >= 3
    assert s.topic == "Chips"


def test_schema_is_strict_and_lists_icons():
    from technews.llm.base import strict_schema

    schema = strict_schema(draft_model())
    visual = schema["properties"]["scenes"]["items"]["properties"]["visual"]
    assert visual["additionalProperties"] is False
    assert set(visual["required"]) == set(visual["properties"])
    assert "chip" in visual["properties"]["icon"]["enum"]
    assert "chip" in icon_names()
    json.dumps(schema)


def test_prompts_include_article_and_rules(cfg, story):
    system, user = prompts(story, cfg)
    assert "Use only facts stated in the ARTICLE" in system
    assert "Allowed icon names" in system
    assert story.title in user and "$499" in user
