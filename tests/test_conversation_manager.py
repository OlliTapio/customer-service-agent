import pytest
from conversation_manager import app, ConversationState

def test_conversation_workflow():
    initial_state = ConversationState(
        user_input="Hi, I'd like to book a meeting.",
        user_email="test@example.com",
        user_name="Test User",
        interaction_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    final_state = app.invoke(initial_state)
    assert final_state["classified_intent"] == "REQUEST_BOOKING"
    assert any("Generated response" in entry for entry in final_state["interaction_history"])


def test_question_services_workflow():
    initial_state = ConversationState(
        user_input="How much would developing custom AI customer service bot cost us?",
        user_email="test@example.com",
        user_name="Test User",
        interaction_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    final_state = app.invoke(initial_state)
    assert final_state["classified_intent"] == "QUESTION_SERVICES"
    assert any("Generated response" in entry for entry in final_state["interaction_history"])
    assert "booking" in final_state["generated_response"].lower() or "varaus" in final_state["generated_response"].lower()


def test_booking_meeting_workflow():
    initial_state = ConversationState(
        user_input="I would like to book a meeting with Olli",
        user_email="test@example.com",
        user_name="Test User",
        interaction_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    final_state = app.invoke(initial_state)
    assert final_state["classified_intent"] == "REQUEST_BOOKING"
    assert any("Generated response" in entry for entry in final_state["interaction_history"])
    assert "booking" in final_state["generated_response"].lower() or "varaus" in final_state["generated_response"].lower()

@pytest.fixture
def example_slots():
    return [
        {"time": "Tuesday, 01.07. at 13:00", "iso": "2025-07-01T10:00:00Z"},
        {"time": "Tuesday, 01.07. at 14:00", "iso": "2025-07-01T11:00:00Z"}
    ]

def test_workflow_service_question(example_slots):
    state = ConversationState(
        user_input="How much would developing custom AI customer service bot cost us?",
        user_email="example@gmail.com",
        user_name="Debug User",
        interaction_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-fi/30min",
        available_slots=example_slots
    )
    final_state = app.invoke(state)
    assert final_state.get("classified_intent") in [
        "QUESTION_SERVICES",
        "REQUEST_BOOKING"
    ]
    assert "booking link" in final_state.get("generated_response", "") or "varauslinkkiä" in final_state.get("generated_response", "")

def test_workflow_booking(example_slots):
    # Simulate a follow-up booking
    state = ConversationState(
        user_input="I'd like to book the first available slot.",
        user_email="example@gmail.com",
        user_name="Debug User",
        interaction_history=["User: How much would developing custom AI customer service bot cost us?", "System: Fetched 2 available slots."],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-fi/30min",
        available_slots=example_slots
    )
    final_state = app.invoke(state)
    # Should either book or ask for clarification
    assert final_state.get("classified_intent") in [
        "REQUEST_BOOKING",
        "QUESTION_SERVICES"
    ]
    # The response should mention a booking or an error
    assert "booked" in final_state.get("generated_response", "") or "couldn't determine" in final_state.get("generated_response", "")
