import pytest
from email_conversation_manager.types import ChatMessage, Intent, AvailableSlot
import services.llm_service as llm_service

@pytest.fixture
def example_slots():
    return [
        AvailableSlot(time="Tuesday, 01.07. at 13:00", iso="2025-07-01T10:00:00Z"),
        AvailableSlot(time="Tuesday, 01.07. at 14:00", iso="2025-07-01T11:00:00Z")
    ]

def test_classify_user_intent():
    assert llm_service.classify_user_intent("Hi there, can I book a meeting?") in llm_service.POSSIBLE_INTENTS
    assert llm_service.classify_user_intent("I'm not interested, thanks.") in llm_service.POSSIBLE_INTENTS

def test_generate_contextual_response_booking(example_slots):
    response = llm_service.generate_contextual_response(
        intent=Intent.REQUEST_BOOKING,
        conversation_history=[ChatMessage(role="user", content="I want to book a time.")],
        user_name="Alice",
        available_slots=example_slots,
        booking_link="https://cal.com/otl-user/30min"
    )
    assert "30-minute time slots" in response or "varauslinkkiä" in response

def test_generate_contextual_response_services(example_slots):
    response = llm_service.generate_contextual_response(
        intent=Intent.QUESTION_SERVICES,
        conversation_history=[ChatMessage(role="user", content="What services do you offer?")],
        user_name="Alice",
        available_slots=example_slots,
        booking_link="https://cal.com/otl-user/30min"
    )
    assert "booking link" in response or "varauslinkkiä" in response

def test_generate_contextual_response_booking_unsupported_language(example_slots):
    """Test that booking responses are properly translated for unsupported languages."""
    # Test with German (de) which is not in BOOKING_TEMPLATES
    response = llm_service.generate_contextual_response(
        intent=Intent.REQUEST_BOOKING,
        conversation_history=[ChatMessage(role="user", content="Ich möchte einen Termin buchen.")],
        user_name="Alice",
        available_slots=example_slots,
        booking_link="https://cal.com/otl-user/30min",
        user_language="de"
    )
    
    # The response should be in German and contain key booking information
    assert "Hallo Alice" in response or "Guten Tag Alice" in response
    assert "Termin" in response or "Zeit" in response
    assert "https://cal.com/otl-user/30min" in response
    assert "Dienstag" in response or "01.07" in response  # German date format
