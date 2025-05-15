import pytest
from conversation_manager import app, ConversationState

def test_conversation_workflow(monkeypatch, example_slots):
    import conversation_manager
    # Patch slot fetching to always return example_slots
    monkeypatch.setattr(conversation_manager, "fetch_raw_slots", lambda event_type_id_v1: [slot["iso"] for slot in example_slots])
    monkeypatch.setattr(conversation_manager, "select_slots", lambda raw_slots: example_slots)
    monkeypatch.setattr(conversation_manager.cal_service, "get_event_type_details_v2", lambda user_cal_username, event_type_slug: {"id": 123})
    monkeypatch.setattr(conversation_manager.cal_service, "create_booking", lambda *a, **kw: {"success": True, "data": {}})
    monkeypatch.setattr(conversation_manager.llm_service, "parse_booked_slot", lambda user_input, available_slots, conversation_history: available_slots[0]["time"])
    monkeypatch.setattr(conversation_manager.llm_service, "generate_intent_summary", lambda user_input, conversation_history, user_language: "Discuss AI solutions")
    initial_state = conversation_manager.ConversationState(
        user_input="Hi, I'd like to book a meeting.",
        user_email="test@example.com",
        user_name="Test User",
        interaction_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    final_state = conversation_manager.app.invoke(initial_state)
    assert final_state["classified_intent"] == "REQUEST_BOOKING"
    assert any("Generated response" in entry for entry in final_state["interaction_history"])
    assert final_state.get("booked_slot") == example_slots[0]["time"]
    assert example_slots[0]["time"] in final_state.get("generated_response", "")


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


def test_booking_meeting_workflow(monkeypatch, example_slots):
    import conversation_manager
    monkeypatch.setattr(conversation_manager, "fetch_raw_slots", lambda event_type_id_v1: [slot["iso"] for slot in example_slots])
    monkeypatch.setattr(conversation_manager, "select_slots", lambda raw_slots: example_slots)
    monkeypatch.setattr(conversation_manager.cal_service, "get_event_type_details_v2", lambda user_cal_username, event_type_slug: {"id": 123})
    monkeypatch.setattr(conversation_manager.cal_service, "create_booking", lambda *a, **kw: {"success": True, "data": {}})
    monkeypatch.setattr(conversation_manager.llm_service, "parse_booked_slot", lambda user_input, available_slots, conversation_history: available_slots[0]["time"])
    monkeypatch.setattr(conversation_manager.llm_service, "generate_intent_summary", lambda user_input, conversation_history, user_language: "Discuss AI solutions")
    initial_state = conversation_manager.ConversationState(
        user_input="I would like to book a meeting with Olli",
        user_email="test@example.com",
        user_name="Test User",
        interaction_history=[],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-user/30min"
    )
    final_state = conversation_manager.app.invoke(initial_state)
    assert final_state["classified_intent"] == "REQUEST_BOOKING"
    assert any("Generated response" in entry for entry in final_state["interaction_history"])
    assert final_state.get("booked_slot") == example_slots[0]["time"]
    assert example_slots[0]["time"] in final_state.get("generated_response", "")

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

def test_booking_sets_booked_slot_and_confirmation(example_slots, monkeypatch):
    # Patch cal_service.create_booking to always succeed and not hit the real API
    import conversation_manager
    def fake_create_booking(api_key, event_type_id, slot_time, user_email, user_name=None, event_type_slug=None, username=None, time_zone="Europe/Helsinki", language="en", notes=None):
        return {"success": True, "data": {}}
    monkeypatch.setattr(conversation_manager.cal_service, "create_booking", fake_create_booking)
    # Patch cal_service.get_event_type_details_v2 to return a fake event type id
    monkeypatch.setattr(conversation_manager.cal_service, "get_event_type_details_v2", lambda user_cal_username, event_type_slug: {"id": 123})
    # Patch llm_service.parse_booked_slot to always select the first slot
    monkeypatch.setattr(conversation_manager.llm_service, "parse_booked_slot", lambda user_input, available_slots, conversation_history: available_slots[0]["time"])
    # Patch llm_service.generate_intent_summary to return a static summary
    monkeypatch.setattr(conversation_manager.llm_service, "generate_intent_summary", lambda user_input, conversation_history, user_language: "Discuss AI solutions")

    state = conversation_manager.ConversationState(
        user_input="I'd like to book the first available slot.",
        user_email="example@gmail.com",
        user_name="Debug User",
        interaction_history=["User: How much would developing custom AI customer service bot cost us?", "System: Fetched 2 available slots."],
        event_type_slug="30min",
        booking_link="https://cal.com/otl-fi/30min",
        available_slots=example_slots
    )
    final_state = conversation_manager.app.invoke(state)
    # Check that the slot was booked and the confirmation message uses the slot string
    assert final_state.get("booked_slot") == example_slots[0]["time"]
    assert "booked for" in final_state.get("generated_response", "")
    assert example_slots[0]["time"] in final_state.get("generated_response", "")
