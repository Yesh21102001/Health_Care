"""Medical safety layer: emergencies must be caught BEFORE the AI is called,
and given fixed emergency guidance immediately.

These scenarios are an engineering baseline, not a clinically validated test set.
"""

import pytest

from app.services.safety_service import enforce_report_rules, filter_ai_reply, screen_user_message
from tests.conftest import signup

EMERGENCIES = [
    ("I have crushing chest pain and my left arm feels heavy", "cardiac"),
    ("chest pain spreading to my jaw and I'm sweating", "cardiac"),
    ("I think I'm having a heart attack", "cardiac"),
    ("I can't breathe properly", "breathing"),
    ("my lips are turning blue", "breathing"),
    ("my face is drooping and my speech is slurred", "stroke"),
    ("I suddenly feel numb on one side of my body", "stroke"),
    ("this is the worst headache of my life", "neuro"),
    ("my son is having a seizure", "neuro"),
    ("fever and a stiff neck", "neuro"),
    ("the bleeding won't stop", "bleeding"),
    ("I've been vomiting blood", "bleeding"),
    ("my throat is closing after eating peanuts", "allergy"),
    ("I took too many pills", "poisoning"),
    ("I want to kill myself", "self_harm"),
    ("I've been having suicidal thoughts", "self_harm"),
    ("I'm pregnant and there's heavy bleeding", "pregnancy"),
    ("I can’t breathe", "breathing"),  # curly apostrophe
]

NON_EMERGENCIES = [
    "I have a mild headache since yesterday",
    "No chest pain, just a cough",
    "I don't have any trouble breathing",
    "no fever or stiff neck",
    "I have a runny nose and sneezing",
    "I've been feeling tired for a few weeks",
]


@pytest.mark.parametrize(("text", "category"), EMERGENCIES)
def test_emergency_phrases_are_detected(text, category):
    result = screen_user_message(text)
    assert result.is_emergency, text
    assert category in result.categories


@pytest.mark.parametrize("text", NON_EMERGENCIES)
def test_ordinary_and_negated_phrases_are_not_emergencies(text):
    assert not screen_user_message(text).is_emergency, text


def test_urgent_signs_are_flagged_as_urgent_not_emergency():
    r = screen_user_message("I've had black tarry stools for two days")
    assert r.level == "urgent"


@pytest.mark.parametrize(("text", "category"), EMERGENCIES[:6] + [EMERGENCIES[14]])
async def test_emergency_skips_ai_and_returns_guidance_immediately(client, fake_ai, text, category):
    await signup(client)
    res = await client.post("/api/chat", json={"message": text})
    assert res.status_code == 200, res.text
    body = res.json()
    conv = body["conversation"]

    assert fake_ai.chat_calls == 0, "AI must not be called when an emergency is detected"
    assert conv["status"] == "emergency_flagged"
    reply = conv["messages"][-1]["content"].lower()
    assert "emergency" in reply
    assert "?" not in conv["messages"][-1]["content"], "no follow-up questions during an emergency"
    assert body["assessmentId"]

    report = (await client.get(f"/api/assessment/{body['assessmentId']}")).json()["assessment"]
    assert report["urgencyLevel"] == "emergency"


async def test_self_harm_gets_crisis_specific_message(client, fake_ai):
    await signup(client)
    res = await client.post("/api/chat", json={"message": "I want to end my life"})
    reply = res.json()["conversation"]["messages"][-1]["content"]
    assert "crisis" in reply.lower() and "emergency" in reply.lower()


async def test_emergency_mid_conversation_overrides_ai(client, fake_ai):
    await signup(client)
    first = (await client.post("/api/chat", json={"message": "I have a headache"})).json()
    assert fake_ai.chat_calls == 1
    cid = first["conversation"]["id"]
    second = await client.post("/api/chat", json={"conversationId": cid, "message": "now my face is drooping"})
    assert second.json()["conversation"]["status"] == "emergency_flagged"
    assert fake_ai.chat_calls == 1
    # The conversation is closed afterwards.
    third = await client.post("/api/chat", json={"conversationId": cid, "message": "hello?"})
    assert third.status_code == 409


async def test_urgent_sign_sets_report_floor_and_ai_note(client, fake_ai):
    await signup(client)
    fake_ai.report_urgency = "self_monitoring"
    first = (await client.post("/api/chat", json={"message": "I have black stools and stomach ache"})).json()
    assert fake_ai.last_safety_note and "warning sign" in fake_ai.last_safety_note
    fake_ai.ready = True
    second = (await client.post("/api/chat", json={"conversationId": first["conversation"]["id"], "message": "3 days, 4/10"})).json()
    report = (await client.get(f"/api/assessment/{second['assessmentId']}")).json()["assessment"]
    assert report["urgencyLevel"] == "urgent", "AI can never rate below the safety floor"


def test_output_filter_removes_dosing_and_certainty():
    r = filter_ai_reply("You definitely have migraine. Take 400 mg ibuprofen twice a day. How long has it lasted?")
    assert "400 mg" not in r.text and "definitely" not in r.text
    assert r.removed_dosing and r.removed_certainty
    assert "How long has it lasted?" in r.text
    assert "doctor or pharmacist" in r.text


def test_output_filter_keeps_safe_text_unchanged():
    text = "I'm sorry you're feeling unwell. How long have you had the cough?"
    assert filter_ai_reply(text).text == text


async def test_ai_reply_is_filtered_before_reaching_user(client, fake_ai):
    await signup(client)
    fake_ai.next_reply = "Take 2 tablets of paracetamol. When did it start?"
    res = (await client.post("/api/chat", json={"message": "I have a headache"})).json()
    reply = res["conversation"]["messages"][-1]["content"]
    assert "tablets" not in reply and "When did it start?" in reply


def test_report_rules_strip_confirmed_and_dosing():
    report = {
        "symptoms": ["x"], "duration": "d", "severity": "s", "additional_info": [], "warning_signs": ["w"],
        "possible_explanations": [{"name": "Confirmed flu", "why": "fever"}],
        "next_steps": ["Take 500 mg paracetamol"], "urgency_level": "self_monitoring", "urgency_reason": "r",
    }
    out = enforce_report_rules(report, "consultation")
    assert out["possible_explanations"][0]["name"] == "flu"
    assert "500 mg" not in out["next_steps"][0]
    assert out["urgency_level"] == "consultation"
