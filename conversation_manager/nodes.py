from typing import List
from datetime import datetime, timedelta
from collections import defaultdict
import dateutil.parser
import pytz
from babel.dates import format_datetime
from langdetect import detect

# Import services and config
import services.llm_service as llm_service
import services.cal_service as cal_service
import config
import services.gmail_service as gmail_service
from services.state_service import state_service

from .state import ConversationState

def new_interaction(state: ConversationState) -> ConversationState:
    """Handles the initialization of a new interaction."""
    print("---NODE: New Interaction---")
    
    # Try to load existing state from Firestore
    if state.get("thread_id"):
        existing_state = state_service.get_state(state["thread_id"])
        if existing_state:
            # Update state with existing data
            for key, value in existing_state.items():
                if key not in ["user_input", "classified_intent", "available_slots", 
                             "generated_response", "error_message"]:
                    state[key] = value
    
    # Initialize interaction_history if not present
    if not state.get("interaction_history"):
        state["interaction_history"] = []
    
    # Update last_updated timestamp
    state["last_updated"] = datetime.now().isoformat()
    
    # Initialize event_type_slug from config if not already set
    if not state.get("event_type_slug") and hasattr(config, 'CAL_COM_EVENT_TYPE_SLUG'):
        state["event_type_slug"] = config.CAL_COM_EVENT_TYPE_SLUG
        print(f"Initialized event_type_slug from config: {state['event_type_slug']}")

    # Initialize booking_link from config if not already set
    if not state.get("booking_link") and hasattr(config, 'CAL_COM_USERNAME') and state.get("event_type_slug"):
        state["booking_link"] = f"https://cal.com/{config.CAL_COM_USERNAME}/{state['event_type_slug']}"
        print(f"Initialized booking_link: {state['booking_link']}")

    if state.get("user_input"):
        state["interaction_history"].append(f"User: {state['user_input']}")
        try:
            state["user_language"] = detect(state["user_input"])
        except Exception:
            state["user_language"] = "en"  # fallback
    print(f"User input: {state.get('user_input')}")
    
    # Only reset fields that should be determined in this run
    state["classified_intent"] = None
    state["available_slots"] = None
    state["generated_response"] = None
    state["error_message"] = None

    # Save the updated state
    if state.get("thread_id"):
        state_service.save_state(state["thread_id"], state)

    return state

def classify_intent_node(state: ConversationState) -> ConversationState:
    """Classifies the user's intent."""
    print("---NODE: Classify Intent---")
    if not state.get("user_input"):
        state["error_message"] = "No user input to classify."
        state["classified_intent"] = llm_service.INTENT_UNSURE
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
        return state

    try:
        intent = llm_service.classify_user_intent(
            user_input=state["user_input"],
            conversation_history=state.get("interaction_history", [])
        )
        state["classified_intent"] = intent
        state["interaction_history"].append(f"System: Classified intent as {intent}")
        print(f"Classified intent: {intent}")
    except Exception as e:
        print(f"Error during intent classification: {e}")
        state["error_message"] = f"Failed to classify intent: {e}"
        state["classified_intent"] = llm_service.INTENT_UNSURE
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
    return state

def gather_information_node(state: ConversationState) -> ConversationState:
    """Gathers additional information based on the classified intent."""
    print("---NODE: Gather Information---")
    intent = state.get("classified_intent")
    if intent in [llm_service.INTENT_REQUEST_BOOKING, llm_service.INTENT_QUESTION_SERVICES]:
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
                formatted_slots = format_slots(selected_slots, state.get("user_language", "en"))
                state["available_slots"] = formatted_slots
                state["interaction_history"].append(f"System: Fetched {len(formatted_slots)} available slots.")
                print(f"Fetched {len(formatted_slots)} available slots: {formatted_slots}")
            else:
                return set_error_and_return(state, f"Could not fetch V2 event details or ID for slug {event_slug_to_use} to get V1 slots.")
        except Exception as e:
            return set_error_and_return(state, f"Error fetching calendar availability: {e}")
    return state

def book_a_meeting_node(state: ConversationState) -> ConversationState:
    """Books a meeting and updates the state with the booked slot and confirmation message."""
    print("---NODE: Book a Meeting---")
    available_slots = state.get("available_slots") or []
    if not available_slots:
        state["error_message"] = "No available slots to book."
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
        return state

    user_input = state.get("user_input", "")
    conversation_history = state.get("interaction_history", [])
    user_language = state.get("user_language", "en")

    # Call parse_booked_slot with all necessary parameters
    selected_slot = llm_service.parse_booked_slot(
        user_input=user_input,
        available_slots=available_slots,
        conversation_history=conversation_history,
        user_language=user_language
    )

    if selected_slot.confidence < 0.7:
        state["error_message"] = "Failed to parse suitable slot for the booking."
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
        return state

    event_details = cal_service.get_event_type_details_v2(
                    user_cal_username=username or config.CAL_COM_USERNAME,
                    event_type_slug=event_type_slug or config.CAL_COM_EVENT_TYPE_SLUG
                )
                
    if event_details and "id" in event_details:
        # Generate meeting summary
        meeting_summary = llm_service.generate_intent_summary(
            user_input=user_input,
            conversation_history=conversation_history,
            user_language=user_language
        )
                    
        # Attempt to book the slot
        booking_result = cal_service.create_booking(
            api_key=config.CAL_COM_API_KEY,
            event_type_id=str(event_details["id"]),
            slot_time=selected_slot.iso,
            user_email=state["user_email"],
            user_name=state.get("user_name"),
            event_type_slug=state.get("event_type_slug"),
            username=config.CAL_COM_USERNAME,
            notes=meeting_summary
        )
        
        
        if not booking_result["success"]:
            return set_error_and_return(state, f"Error booking slot: {booking_result['error']}")

    if slot_string:
        state["booked_slot"] = slot_string
        state["interaction_history"].append(f"System: Booked slot {slot_string} for {state['user_email']}.")
    else:
        state["error_message"] = "Could not book the selected slot."
        state["interaction_history"].append(f"System: Error - {state['error_message']}")

    return state

def generate_response_node(state: ConversationState) -> ConversationState:
    """Generates a response based on the classified intent and gathered information."""
    print("---NODE: Generate Response---")
    if not state.get("classified_intent"):
        state["generated_response"] = "I'm sorry, I wasn't able to understand your request. Could you please rephrase?"
        state["error_message"] = "Cannot generate response: Intent not classified."
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
        return state
    # If a meeting was booked, use a template for the confirmation
    if state.get("booked_slot"):
        user_lang = state.get("user_language", "en")
        user_name = state.get("user_name")
        slot_str = state["booked_slot"]
        confirmation = f"Hi{f' {user_name}' if user_name else ''},\n\nYour meeting has been booked for {slot_str}. You will receive a confirmation email shortly.\n\nBest regards,\nOlli's Personal Assistant"
        state["generated_response"] = confirmation
        state["interaction_history"].append(f"System: Generated booking confirmation for {slot_str}.")
        return state
    # Otherwise, use the normal contextual response logic
    try:
        response_text = llm_service.generate_contextual_response(
            intent=state["classified_intent"],
            user_input=state.get("user_input", ""),
            conversation_history=state.get("interaction_history", []),
            user_name=state.get("user_name"),
            available_slots=state.get("available_slots"),
            booking_link=state.get("booking_link"),
            event_type_slug=state.get("event_type_slug"),
            website_info="OTL.fi provides AI audit and implementation for companies interested in freeing time in their organisation from menial work. For detailed discussions, a call is recommended."
        )
        state["generated_response"] = response_text
        state["interaction_history"].append(f"System: Generated response: {response_text}")
        print(f"Generated response: {response_text}")
    except Exception as e:
        print(f"Error during response generation: {e}")
        state["error_message"] = f"Failed to generate response: {e}"
        state["generated_response"] = (
            "I apologize, I encountered an error while trying to generate a response. "
            "Please try again or contact us directly."
        )
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
    return state

def send_response_node(state: ConversationState) -> ConversationState:
    """Sends the generated response to the user."""
    print("---NODE: Send Response---")
    if state.get("user_email") and state.get("generated_response"):
        try:
            subject = "Re: Your Inquiry"
            gmail_service_instance = gmail_service.authenticate_gmail()
            if gmail_service_instance:
                gmail_service.send_email(
                    gmail_service_instance,
                    state["user_email"],
                    subject,
                    state["generated_response"]
                )
                state["interaction_history"].append(f"System: Sent response to {state['user_email']}.")
                print(f"Response sent to {state['user_email']}.")
            else:
                state["error_message"] = "Failed to authenticate with Gmail API."
                state["interaction_history"].append(f"System: Error - {state['error_message']}")
                print(state["error_message"])
        except Exception as e:
            print(f"Error sending email: {e}")
            state["error_message"] = f"Failed to send email: {e}"
            state["interaction_history"].append(f"System: Error - {state['error_message']}")
    else:
        print("Skipping send: No email address or no response generated.")
        state["interaction_history"].append("System: Skipped sending response (no email/response).")
    return state

def await_further_input_node(state: ConversationState) -> ConversationState:
    """Waits for further input from the user."""
    print("---NODE: Await Further Input---")
    
    # Update the last_updated timestamp
    state["last_updated"] = datetime.now().isoformat()
    
    # Add a waiting message to the interaction history
    state["interaction_history"].append("System: Awaiting further input from user.")
    
    # Save the state to Firestore
    if state.get("thread_id"):
        state_service.save_state(state["thread_id"], state)
        print(f"Saved conversation state for thread {state['thread_id']}")
        print(f"Last updated: {state['last_updated']}")
        print(f"Current interaction history length: {len(state['interaction_history'])}")
    
    return state

def end_interaction_node(state: ConversationState) -> ConversationState:
    """Ends the interaction."""
    print("---NODE: End Interaction---")
    state["interaction_history"].append("System: Interaction ended.")
    print("Interaction ended.")
    return state

# Helper functions
def get_event_type_slug_from_state_or_config(state: ConversationState) -> str:
    event_slug = state.get("event_type_slug")
    if not event_slug and hasattr(config, 'CAL_COM_EVENT_TYPE_SLUG'):
        event_slug = config.CAL_COM_EVENT_TYPE_SLUG
    return event_slug

def set_error_and_return(state: ConversationState, error_msg: str) -> ConversationState:
    print(error_msg)
    state["error_message"] = error_msg
    state["interaction_history"].append(f"System: Error - {error_msg}")
    state["available_slots"] = []
    return state

def fetch_raw_slots(event_type_id_v1: str) -> list:
    return cal_service.get_available_slots_v1(
        api_key=config.CAL_COM_API_KEY,
        event_type_id=str(event_type_id_v1),
        days_to_check=14,
        target_timezone="Europe/Helsinki"
    )

def select_slots(raw_slots: list) -> list:
    """
    Selects the slots to be displayed to the user.
    Fetches available slots for 14 days and chooses the first 3 days that have slots.
    Shows only one slot per day, and prefers the afternoon slots for tomorrow.
    """
    helsinki = pytz.timezone("Europe/Helsinki")
    now_hel = datetime.now(helsinki)
    today = now_hel.date()
    tomorrow = today + timedelta(days=1)
    slots_by_date = defaultdict(list)
    for slot_time in raw_slots:
        try:
            dt = dateutil.parser.isoparse(slot_time).astimezone(helsinki)
            slot_date = dt.date()
            slots_by_date[slot_date].append(dt)
        except Exception as e:
            print(f"Error parsing slot time {slot_time}: {e}")
    selected_slots = []
    used_times = set()
    for offset in range(1, 15):
        day = today + timedelta(days=offset)
        if day in slots_by_date:
            if day == tomorrow:
                afternoon_slots = [dt for dt in slots_by_date[day] if dt.hour >= 13]
                if afternoon_slots:
                    for dt in afternoon_slots:
                        tstr = dt.strftime("%H:%M")
                        if tstr not in used_times:
                            selected_slots.append(dt)
                            used_times.add(tstr)
                            break
                    else:
                        continue
                else:
                    for dt in sorted(slots_by_date[day]):
                        tstr = dt.strftime("%H:%M")
                        if tstr not in used_times:
                            selected_slots.append(dt)
                            used_times.add(tstr)
                            break
            else:
                for dt in sorted(slots_by_date[day]):
                    tstr = dt.strftime("%H:%M")
                    if tstr not in used_times:
                        selected_slots.append(dt)
                        used_times.add(tstr)
                        break
        if len(selected_slots) >= 3:
            break
    return selected_slots

def format_slots(selected_slots: list, user_lang: str) -> list:
    formatted_slots = []
    for dt in selected_slots:
        if user_lang.startswith("fi"):
            fmt = "EEEE, dd.MM. 'klo' HH:mm"
        else:
            fmt = "EEEE, dd.MM. 'at' HH:mm"
        try:
            formatted = format_datetime(dt, fmt, locale=user_lang)
        except Exception:
            formatted = dt.strftime("%A, %d.%m. at %H:%M")
        formatted_slots.append({"time": formatted, "iso": dt.isoformat()})
    return formatted_slots 