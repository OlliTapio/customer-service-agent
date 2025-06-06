from datetime import datetime
from langdetect import detect

# Import services and config
from helpers.booking_helpers import format_slots, select_slots
import services.llm_service as llm_service
import services.cal_service as cal_service
import config

from .types import ChatMessage, EmailConversationState, Intent, MessageRole

def new_interaction(state: EmailConversationState) -> EmailConversationState:
    """Handles the initialization of a new interaction."""
    print("---NODE: New Interaction---")
    
    # Initialize interaction_history if not present
    if not state.previous_chat_history:
        state.previous_chat_history = []
    
    # Update last_updated timestamp
    state.last_updated = datetime.now().isoformat()
    
    # Initialize event_type_slug from config if not already set
    if not state.event_type_slug and hasattr(config, 'CAL_COM_EVENT_TYPE_SLUG'):
        state.event_type_slug = config.CAL_COM_EVENT_TYPE_SLUG
        print(f"Initialized event_type_slug from config: {state.event_type_slug}")

    # Initialize booking_link from config if not already set
    if not state.booking_link and hasattr(config, 'CAL_COM_USERNAME') and state.event_type_slug:
        state.booking_link = f"https://cal.com/{config.CAL_COM_USERNAME}/{state.event_type_slug}"
        print(f"Initialized booking_link: {state.booking_link}")

    if state.user_input:
        state.appended_chat_history.append(ChatMessage(role=MessageRole.USER, content=state.user_input))
        try:
            state.user_language = detect(state.user_input)
        except Exception:
            state.user_language = "en"  # fallback
    print(f"User input: {state.user_input}")
    
    # Only reset fields that should be determined in this run
    state.classified_intent = None
    state.generated_response = None
    state.error_message = None

    return state

def classify_intent_node(state: EmailConversationState) -> EmailConversationState:
    """Classifies the user's intent."""
    print("---NODE: Classify Intent---")
    if not state.user_input:
        state.error_message = "No user input to classify."
        state.classified_intent = Intent.UNSURE
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I encountered an error: {state.error_message}"))
        return state

    try:
        intent = llm_service.classify_user_intent(
            user_input=state.user_input,
            conversation_history=state.previous_chat_history
        )
        state.classified_intent = intent
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I have classified the user's intent as {intent}"))
        print(f"Classified intent: {intent}")
    except Exception as e:
        print(f"Error during intent classification: {e}")
        state.error_message = f"Failed to classify intent: {e}"
        state.classified_intent = Intent.UNSURE
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I encountered an error while classifying intent: {state.error_message}"))
    return state

def gather_information_node(state: EmailConversationState) -> EmailConversationState:
    """Gathers additional information based on the classified intent."""
    print("---NODE: Gather Information---")
    intent = state.classified_intent
    if intent in [Intent.REQUEST_BOOKING, Intent.QUESTION_SERVICES]:
        print("Attempting to fetch calendar availability...")
        try:
            event_slug_to_use = get_event_type_slug_from_state_or_config(state)
            if not event_slug_to_use:
                return set_error_and_return(state, "Event type slug not configured or found in state.")
            event_details_v2 = cal_service.get_event_type_details_v2(
                user_cal_username=config.CAL_COM_USERNAME,
                event_type_slug=event_slug_to_use
            )
            if event_details_v2 and event_details_v2.get("id"):
                event_type_id_v1 = event_details_v2["id"]
                raw_slots = fetch_raw_slots(event_type_id_v1)
                selected_slots = select_slots(raw_slots)
                formatted_slots = format_slots(selected_slots, state.user_language or "en")
                state.available_slots = formatted_slots
                state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"Fetched {len(formatted_slots)} available slots: {formatted_slots}"))
                print(f"Fetched {len(formatted_slots)} available slots: {formatted_slots}")
            else:
                return set_error_and_return(state, f"Could not fetch V2 event details or ID for slug {event_slug_to_use} to get V1 slots.")
        except Exception as e:
            return set_error_and_return(state, f"Error fetching calendar availability: {e}")
    return state

def book_a_meeting_node(state: EmailConversationState) -> EmailConversationState:
    """Books a meeting and updates the state with the booked slot and confirmation message."""
    print("---NODE: Book a Meeting---")
    available_slots = state.available_slots or []
    if not available_slots:
        state.error_message = "No available slots to book."
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"Error - {state.error_message}"))
        return state

    user_input = state.user_input or ""
    conversation_history = state.previous_chat_history + state.appended_chat_history
    user_language = state.user_language or "en"

    # Call parse_booked_slot with all necessary parameters
    selected_slot: llm_service.SlotSelection = llm_service.parse_booked_slot(
        user_input=user_input,
        available_slots=available_slots,
        conversation_history=conversation_history,
    )

    if selected_slot.confidence < 0.7:
        state.error_message = "Failed to parse suitable slot for the booking."
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"Error - {state.error_message}"))
        return state

    # Match the selected slot to the available slots
    # Taking into account that timezones might be different
    def parse_iso(iso_str):
        # Handles both with and without 'Z'
        if iso_str.endswith('Z'):
            iso_str = iso_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_str)
        return dt

    # Parse the selected slot into a datetime object
    selected_datetime = selected_slot.selected_slot
    
    booked_slot = next(
        (
            slot for slot in available_slots
            if parse_iso(slot.iso) == selected_datetime
        ),
        None
    )
    if not booked_slot:
        for slot in available_slots:
            parsed = parse_iso(slot.iso)
            print(f"  - {slot.iso} -> {parsed} (type: {type(parsed)})")
        state.error_message = "Could not find the selected slot in the available slots."
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"Error - {state.error_message}"))
        return state

    event_details = cal_service.get_event_type_details_v2(
                    user_cal_username=config.CAL_COM_USERNAME,
                    event_type_slug=state.event_type_slug or config.CAL_COM_EVENT_TYPE_SLUG
                )
                
    if event_details and "id" in event_details:
        # Generate meeting summary
        meeting_summary = llm_service.generate_meeting_description(
            user_input=user_input,
            conversation_history=conversation_history,
            user_language=user_language
        )
                    
        # Attempt to book the slot
        booking_result = cal_service.create_booking(
            api_key=config.CAL_COM_API_KEY,
            event_type_id=str(event_details["id"]),
            slot_time=booked_slot.iso,
            user_email=state.user_email,
            user_name=state.user_name,
            event_type_slug=state.event_type_slug,
            username=config.CAL_COM_USERNAME,
            notes=meeting_summary
        )
        
        if not booking_result["success"]:
            return set_error_and_return(state, f"Error booking slot: {booking_result['error']}")

        if booked_slot:
            state.booked_slot = booked_slot
            state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I have successfully booked a meeting slot for {booked_slot.time} for {state.user_email}"))
        else:
            state.error_message = "Could not book the selected slot."
            state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I encountered an error while booking the slot: {state.error_message}"))

    return state

def generate_response_node(state: EmailConversationState) -> EmailConversationState:
    """Generates a response based on the classified intent and gathered information."""
    print("---NODE: Generate Response---")
    if not state.classified_intent:
        state.generated_response = "I'm sorry, I wasn't able to understand your request. Could you please rephrase?"
        state.error_message = "Cannot generate response: Intent not classified."
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"Error - {state.error_message}"))
        return state
    # If a meeting was booked, use a template for the confirmation
    if state.booked_slot:
        user_name = state.user_name
        slot_str = state.booked_slot.time
        confirmation = f"Hi{f' {user_name}' if user_name else ''},\n\nYour meeting has been booked for {slot_str}. You will receive a confirmation email shortly.\n\nBest regards,\nOlli's Personal Assistant"
        state.generated_response = confirmation
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I have generated a booking confirmation message for the meeting scheduled at {slot_str}"))
        return state
    # Otherwise, use the normal contextual response logic
    try:
        response_text = llm_service.generate_contextual_response(
            intent=state.classified_intent,
            conversation_history=state.previous_chat_history + state.appended_chat_history,
            user_name=state.user_name,
            available_slots=state.available_slots,
            booking_link=state.booking_link,
            event_type_slug=state.event_type_slug,
            user_language=state.user_language,
            website_info="OTL.fi provides AI audit and implementation for companies interested in freeing time in their organisation from menial work. For detailed discussions, a call is recommended."
        )
        state.generated_response = response_text
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I have generated a response based on the user's intent and context: {response_text}"))
        print(f"Generated response: {response_text}")
    except Exception as e:
        print(f"Error during response generation: {e}")
        state.error_message = f"Failed to generate response: {e}"
        state.generated_response = (
            "I apologize, I encountered an error while trying to generate a response. "
            "Please try again or contact us directly."
        )
        state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I encountered an error while generating a response: {state.error_message}"))
    return state

def end_interaction_node(state: EmailConversationState) -> EmailConversationState:
    """Ends the interaction."""
    print("---NODE: End Interaction---")
    
    # Update last_updated timestamp
    state.last_updated = datetime.now().isoformat()
    
    # Add final system message
    state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content="I have completed processing this interaction"))
    
    print("Interaction ended.")
    return state

# Helper functions
def get_event_type_slug_from_state_or_config(state: EmailConversationState) -> str:
    event_slug = state.event_type_slug
    if not event_slug and hasattr(config, 'CAL_COM_EVENT_TYPE_SLUG'):
        event_slug = config.CAL_COM_EVENT_TYPE_SLUG
    return event_slug

def set_error_and_return(state: EmailConversationState, error_msg: str) -> EmailConversationState:
    print(error_msg)
    state.error_message = error_msg
    state.appended_chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"I encountered an error: {error_msg}"))
    state.available_slots = []
    return state

def fetch_raw_slots(event_type_id_v1: str) -> list:
    return cal_service.get_available_slots_v1(
        event_type_id=str(event_type_id_v1),
        days_to_check=14,
        target_timezone="Europe/Helsinki"
    )