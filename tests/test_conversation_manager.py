import pytest
from email_conversation_manager import app, EmailConversationState
from email_conversation_manager.types import AvailableSlot, ChatMessage, Intent
from services import cal_service, llm_service
from datetime import datetime

@pytest.fixture
def mock_services(monkeypatch, example_slots):
    # Mock cal_service
    monkeypatch.setattr(cal_service, "get_available_slots_v1", lambda *a, **kw: [slot["iso"] for slot in example_slots])
    monkeypatch.setattr(cal_service, "get_event_type_details_v2", lambda *a, **kw: {"id": 123})
    monkeypatch.setattr(cal_service, "create_booking", lambda *a, **kw: {"success": True, "data": {}})
    
    # Mock llm_service
    def mock_parse_booked_slot(*args, **kwargs):
        # Return a datetime object for selected_slot to match the real code's matching logic
        slot_iso = example_slots[0]["iso"]
        slot_dt = datetime.fromisoformat(slot_iso.replace("Z", "+00:00"))
        return llm_service.SlotSelection(
            confidence=1.0,
            selected_slot=slot_dt
        )
    monkeypatch.setattr(llm_service, "parse_booked_slot", mock_parse_booked_slot)
    monkeypatch.setattr(llm_service, "classify_user_intent", lambda *a, **kw: Intent.REQUEST_BOOKING)
    monkeypatch.setattr(llm_service, "generate_contextual_response", lambda *a, **kw: "Generated response")

@pytest.fixture
def example_slots():
    return [
        {"time": "Tuesday, 01.07. at 13:00", "iso": "2025-07-01T13:00:00.000+03:00"},
        {"time": "Wednesday, 02.07. at 14:00", "iso": "2025-07-02T14:00:00.000+03:00"}
    ]

def test_request_booking_flow(mock_services, example_slots):
    """Test the basic conversation flow through the graph."""
    initial_state = EmailConversationState(
        thread_id="test-thread-1",
        user_input="Hi, I'd like to book a meeting.",
        user_email="test@example.com",
        user_name="Test User",
        previous_chat_history=[],
        appended_chat_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    
    final_state = app.invoke(initial_state)
    
    # Verify the state transitions
    assert final_state["classified_intent"] == Intent.REQUEST_BOOKING
    assert any("Generated response" in entry.content for entry in final_state["appended_chat_history"])
    assert len(final_state["available_slots"]) == len(example_slots)

def test_service_question_flow(mock_services, example_slots):
    """Test the flow when user asks about services."""
    # Override the intent classification for this test
    import services.llm_service as llm_service
    llm_service.classify_user_intent = lambda *a, **kw: Intent.QUESTION_SERVICES
    
    initial_state = EmailConversationState(
        thread_id="test-thread-2",
        user_input="How much would developing custom AI customer service bot cost us?",
        user_email="test@example.com",
        user_name="Test User",
        previous_chat_history=[],
        appended_chat_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    
    final_state = app.invoke(initial_state)
    
    assert final_state["classified_intent"] == Intent.QUESTION_SERVICES
    assert len(final_state["available_slots"]) == len(example_slots)
    assert any("Generated response" in entry.content for entry in final_state["appended_chat_history"])

def test_book_a_meeting_flow(mock_services, example_slots):
    """Test the booking flow with available slots."""
    import services.llm_service as llm_service
    llm_service.classify_user_intent = lambda *a, **kw: Intent.BOOK_A_MEETING
    
    initial_state = EmailConversationState(
        thread_id="test-thread-3",
        user_input="I would like to book next available meeting",
        user_email="test@example.com",
        user_name="Test User",
        previous_chat_history=[
            ChatMessage(role="user", content="Hi, I'd like to book a meeting."),
            ChatMessage(role="assistant", content="Generated response"),
        ],
        appended_chat_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min",
        available_slots=[AvailableSlot(time=slot["time"], iso=slot["iso"]) for slot in example_slots]
    )
    
    final_state = app.invoke(initial_state)
    
    assert final_state["classified_intent"] == Intent.BOOK_A_MEETING
    assert final_state.get("booked_slot") == AvailableSlot(time=example_slots[0]["time"], iso=example_slots[0]["iso"])
    assert "booked" in final_state.get("generated_response").lower()

def test_unsure_intent_flow(mock_services):
    """Test the flow when the intent is unclear."""
    # Override the intent classification for this test
    import services.llm_service as llm_service
    llm_service.classify_user_intent = lambda *a, **kw: Intent.UNSURE
    
    initial_state = EmailConversationState(
        thread_id="test-thread-4",
        user_input="I'm not sure what I want",
        user_email="test@example.com",
        user_name="Test User",
        previous_chat_history=[],
        appended_chat_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    
    final_state = app.invoke(initial_state)
    
    assert final_state["classified_intent"] == Intent.UNSURE
    assert any("Generated response" in entry.content for entry in final_state["appended_chat_history"])
