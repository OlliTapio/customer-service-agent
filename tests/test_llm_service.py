import pytest
import llm_service

@pytest.fixture
def example_slots():
    return [
        {"time": "Tuesday, 01.07. at 13:00", "iso": "2025-07-01T10:00:00Z"},
        {"time": "Tuesday, 01.07. at 14:00", "iso": "2025-07-01T11:00:00Z"}
    ]

def test_classify_user_intent():
    assert llm_service.classify_user_intent("Hi there, can I book a meeting?") in llm_service.POSSIBLE_INTENTS
    assert llm_service.classify_user_intent("I'm not interested, thanks.") in llm_service.POSSIBLE_INTENTS

def test_generate_contextual_response_booking(example_slots):
    response = llm_service.generate_contextual_response(
        intent=llm_service.INTENT_REQUEST_BOOKING,
        user_input="Yes, those times look good.",
        conversation_history=["User: I want to book a time."],
        user_name="Alice",
        available_slots=example_slots,
        booking_link="https://cal.com/otl-user/30min"
    )
    assert "30-minute time slots" in response or "varauslinkkiä" in response

def test_generate_contextual_response_services(example_slots):
    response = llm_service.generate_contextual_response(
        intent=llm_service.INTENT_QUESTION_SERVICES,
        user_input="What services do you offer?",
        conversation_history=["User: What services do you offer?"],
        user_name="Alice",
        available_slots=example_slots,
        booking_link="https://cal.com/otl-user/30min"
    )
    assert "booking link" in response or "varauslinkkiä" in response
