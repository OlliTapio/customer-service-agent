"""
Integration tests for the email conversation flow.

These tests verify the full conversation flow including:
- LLM-based intent classification
- Calendar slot availability and booking
- Response generation
- State management

Note: These tests use the actual LLM service and should be run with appropriate API keys configured.
"""

import pytest
from email_conversation_manager import app, EmailConversationState
from email_conversation_manager.types import AvailableSlot, Intent, ChatMessage
from services import cal_service, llm_service
from datetime import datetime

@pytest.fixture
def example_slots():
    """Fixture providing example calendar slots for testing."""
    return [
        {"time": "Tuesday, 01.07. at 13:00", "iso": "2025-07-01T13:00:00+03:00"},
        {"time": "Wednesday, 02.07. at 14:00", "iso": "2025-07-02T14:00:00+03:00"}
    ]

def test_two_message_booking_flow(monkeypatch, example_slots):
    """Test a complete booking flow with two messages:
    1. First message asks for availability
    2. Second message books the first available slot
    """
    import email_conversation_manager
    
    # Mock cal_service to return example slots
    def mock_get_available_slots(event_type_id, days_to_check, target_timezone):
        print(f"[DEBUG] Mock get_available_slots called with: event_type_id={event_type_id}, days_to_check={days_to_check}, target_timezone={target_timezone}")
        slots = [slot["iso"] for slot in example_slots]
        print(f"[DEBUG] Returning slots: {slots}")
        return slots

    monkeypatch.setattr(cal_service, "get_available_slots_v1", mock_get_available_slots)
    monkeypatch.setattr(cal_service, "get_event_type_details_v2", lambda user_cal_username, event_type_slug: {"id": 123})
    monkeypatch.setattr(cal_service, "create_booking", lambda *a, **kw: {"success": True, "data": {}})

    # Mock LLM services to return consistent responses
    def mock_parse_booked_slot(user_input, available_slots, conversation_history, user_language="en"):
        return type('obj', (object,), {
            'confidence': 0.9,
            'selected_slot': available_slots[0].iso
        })
    
    monkeypatch.setattr(llm_service, "parse_booked_slot", mock_parse_booked_slot)
    monkeypatch.setattr(llm_service, "generate_meeting_description", lambda *a, **kw: "Test meeting")
    
    thread_id = "123"

    # First message: Ask for availability
    initial_state = email_conversation_manager.EmailConversationState(
        thread_id=thread_id,
        user_input="Hi, I'd like to know when you have available slots for a meeting?",
        user_email="test@example.com",
        user_name="Test User",
        last_updated=datetime.now().isoformat(),
        previous_chat_history=[],
        appended_chat_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min",
        user_language="en",
    )
    
    # Process first message
    first_state = email_conversation_manager.app.invoke(initial_state)
    
    available_slots = [AvailableSlot(time=slot["time"], iso=slot["iso"]) for slot in example_slots]

    # Verify first message processing
    assert first_state["classified_intent"] == Intent.REQUEST_BOOKING
    assert first_state["available_slots"] == available_slots
    assert "available" in first_state["generated_response"].lower()
    
    # Second message: Book the first slot
    second_state = email_conversation_manager.EmailConversationState(
        thread_id=thread_id,
        user_input="I'd like to book the first available slot.",
        user_email="test@example.com",
        user_name="Test User",
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min",
        available_slots=first_state["available_slots"],
        previous_chat_history=first_state["appended_chat_history"],
    )
    
    # Process second message
    final_state = email_conversation_manager.app.invoke(second_state)

    # Verify final state
    assert final_state["classified_intent"] == Intent.BOOK_A_MEETING
    assert final_state["booked_slot"].time == available_slots[0].time
    assert "booked" in final_state["generated_response"].lower()
    assert available_slots[0].time in final_state["generated_response"]
    assert "confirmation email" in final_state["generated_response"].lower()
