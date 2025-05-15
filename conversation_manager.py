from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langdetect import detect

# Import services and config
import llm_service  # Assuming llm_service.py is in the same directory or accessible via PYTHONPATH
import cal_service  # Assuming cal_service.py is in the same directory
import config       # For CAL_COM_USERNAME, CAL_COM_EVENT_TYPE_SLUG etc.
import pytz
from datetime import datetime, timedelta
import dateutil.parser
from collections import defaultdict
from babel.dates import format_datetime

# 1. Define the state schema (ensure it aligns with what services need and produce)
class AvailableSlot(TypedDict):
    time: str  # Formatted string for user display
    iso: str   # ISO8601 string for API booking

class ConversationState(TypedDict):
    user_input: Optional[str]
    user_email: Optional[str]
    user_name: Optional[str]
    interaction_history: List[str]
    classified_intent: Optional[str]
    available_slots: Optional[List[AvailableSlot]]
    booked_slot: Optional[str]
    generated_response: Optional[str]
    error_message: Optional[str]
    # Add fields that might be needed by services or for graph logic
    booking_link: Optional[str]      # Can be pre-set or generated
    event_type_slug: Optional[str]   # To help generate booking_link or fetch slots
    user_language: Optional[str]  # e.g., 'en', 'fi', 'sv'


# 2. Define the nodes
def new_interaction(state: ConversationState) -> ConversationState:
    """Handles the initialization of a new interaction."""
    print("---NODE: New Interaction---")
    if not state.get("interaction_history"):
        state["interaction_history"] = []
    
    # Initialize event_type_slug from config if not already set (e.g. by a calling function)
    if not state.get("event_type_slug") and hasattr(config, 'CAL_COM_EVENT_TYPE_SLUG'):
        state["event_type_slug"] = config.CAL_COM_EVENT_TYPE_SLUG
        print(f"Initialized event_type_slug from config: {state['event_type_slug']}")

    # Initialize booking_link from config if not already set
    if not state.get("booking_link") and hasattr(config, 'CAL_COM_USERNAME') and state.get("event_type_slug"):
        state["booking_link"] = f"https://cal.com/{config.CAL_COM_USERNAME}/{state['event_type_slug']}"
        print(f"Initialized booking_link: {state['booking_link']}")

    if state.get("user_input"): # Add current user input to history
        state["interaction_history"].append(f"User: {state['user_input']}")
        try:
            state["user_language"] = detect(state["user_input"])
        except Exception:
            state["user_language"] = "en"  # fallback
    print(f"User input: {state.get('user_input')}")
    # Reset fields that should be determined in this run
    state["classified_intent"] = None
    state["available_slots"] = None
    state["generated_response"] = None
    state["error_message"] = None
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

# --- Helper functions for gather_information_node (move to helpers.py if desired) ---
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

def generate_response_node(state: ConversationState) -> ConversationState:
    """Generates a response based on the classified intent and gathered information."""
    print("---NODE: Generate Response---")
    if not state.get("classified_intent"):
        state["generated_response"] = "I'm sorry, I wasn't able to understand your request. Could you please rephrase?"
        state["error_message"] = "Cannot generate response: Intent not classified."
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
        return state

    # Booking logic: if user wants to book a slot and slots are available
    user_input_lower = (state.get("user_input") or "").lower()
    if (
        state["classified_intent"] == llm_service.INTENT_REQUEST_BOOKING and
        ("book" in user_input_lower or "varaa" in user_input_lower) and
        "slot" in user_input_lower and
        state.get("available_slots")
    ):
        print("[DEBUG] Booking logic triggered.")
        # Get event type id
        event_type_slug = state.get("event_type_slug")
        event_details = cal_service.get_event_type_details_v2(
            user_cal_username=config.CAL_COM_USERNAME,
            event_type_slug=event_type_slug
        )
        event_type_id = event_details["id"] if event_details and "id" in event_details else None
        if not event_type_id:
            state["generated_response"] = "Sorry, I couldn't find the event type to book your meeting."
            state["error_message"] = "Event type ID not found for booking."
            state["interaction_history"].append(f"System: Error - {state['error_message']}")
            return state
        # Use LLM to parse which slot to book
        slot_string = llm_service.parse_booked_slot(
            user_input=state.get("user_input", ""),
            available_slots=state["available_slots"],
            conversation_history=state.get("interaction_history", [])
        )
        print(f"[DEBUG] LLM selected slot string: {slot_string}")
        slot_to_book = None
        for slot in state["available_slots"]:
            if slot.get("time") == slot_string:
                slot_to_book = slot["iso"]
                break
        if not slot_to_book:
            state["generated_response"] = "Sorry, I couldn't determine which slot to book. Please specify the slot or try again."
            state["error_message"] = "No matching slot found for booking."
            state["interaction_history"].append(f"System: Error - {state['error_message']}")
            return state
        booking_result = cal_service.create_booking(
            api_key=config.CAL_COM_API_KEY,
            event_type_id=str(event_type_id),
            slot_time=slot_to_book,
            user_email=state["user_email"],
            user_name=state.get("user_name")
        )
        if booking_result["success"]:
            state["generated_response"] = f"Your meeting has been booked for {slot_to_book}. You will receive a confirmation email shortly."
            state["interaction_history"].append(f"System: Booked slot {slot_to_book} for {state['user_email']}.")
        else:
            state["generated_response"] = "Sorry, we couldn't book your meeting. Please try again or use the booking link."
            state["error_message"] = booking_result.get("error", "Unknown error during booking.")
            state["interaction_history"].append(f"System: Error - {state['error_message']}")
        print(f"[DEBUG] Booking result: {booking_result}")
        return state

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
    # Uses state["generated_response"] and state["user_email"]
    if state.get("user_email") and state.get("generated_response"):
        try:
            # You may want to allow subject customization in the future
            subject = "Re: Your Inquiry"
            # You may want to pass a Gmail API service object via state or global, but for now, authenticate here
            import gmail_service
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
    # Optionally clear the generated response after sending
    # state["generated_response"] = None
    return state

def book_a_meeting_node(state: ConversationState) -> ConversationState:
    """Books a meeting."""
    print("---NODE: Book a Meeting---")
    llm_service.parse_booked_slot(state["user_input"], state["available_slots"], state["interaction_history"])
    state["interaction_history"].append("System: Booking a meeting.")
    return state

def await_further_input_node(state: ConversationState) -> ConversationState:
    """Waits for further input from the user."""
    print("---NODE: Await Further Input---")
    state["interaction_history"].append("System: Awaiting further input from user.")
    print("Waiting for next user input...")
    # In a real scenario, the application would pause here or this state would signify the end of
    # the current processing cycle, waiting for an external trigger (new email, new voice input).
    return state

def end_interaction_node(state: ConversationState) -> ConversationState:
    """Ends the interaction."""
    print("---NODE: End Interaction---")
    state["interaction_history"].append("System: Interaction ended.")
    print("Interaction ended.")
    # Final clean-up or logging can happen here.
    return state


# 3. Define the graph
workflow = StateGraph(ConversationState)

# Add nodes with new names
workflow.add_node("new_interaction", new_interaction)
workflow.add_node("classify_intent", classify_intent_node) 
workflow.add_node("gather_information", gather_information_node) 
workflow.add_node("generate_response", generate_response_node) 
workflow.add_node("send_response", send_response_node) 
workflow.add_node("await_further_input", await_further_input_node) 
workflow.add_node("end_interaction", end_interaction_node) 
workflow.add_node("book_a_meeting", book_a_meeting_node) 


# 4. Define the edges

workflow.set_entry_point("new_interaction")
workflow.add_edge("new_interaction", "classify_intent")

def decide_next_step_after_classification(state: ConversationState) -> str:
    print("---DECISION: After Classification---")
    intent = state.get("classified_intent")
    if state.get("error_message") and intent == llm_service.INTENT_UNSURE: # Error in classification
        print("Decision: Error during classification, ending interaction.")
        return "end_interaction"

    # CHANGED: Go to gather_information for both booking and question_services
    if intent in [llm_service.INTENT_REQUEST_BOOKING, llm_service.INTENT_QUESTION_SERVICES]:
        print("Decision: Gather information for booking or service question.")
        return "gather_information"
    elif intent in [llm_service.INTENT_GREETING, llm_service.INTENT_PROVIDE_INFO, llm_service.INTENT_FOLLOW_UP, 
                    llm_service.INTENT_NOT_INTERESTED_BUYING, llm_service.INTENT_INTERESTED_SELLING_TO_US]:
        print(f"Decision: Generate response directly for intent: {intent}")
        return "generate_response"
    elif intent == llm_service.INTENT_UNSURE:
         print(f"Decision: Intent is UNSURE. Generating a clarification response.")
         return "generate_response" # Let generate_response handle UNSURE by asking for clarification
    elif intent == llm_service.INTENT_BOOK_A_MEETING:
        print(f"Decision: Book a meeting intent detected. Going to book_a_meeting.")
        return "book_a_meeting"
    else: 
        print(f"Decision: Unknown or unhandled intent '{intent}', ending interaction.")
        return "end_interaction"

workflow.add_conditional_edges(
    "classify_intent",
    decide_next_step_after_classification,
    {
        "gather_information": "gather_information",
        "generate_response": "generate_response",
        "book_a_meeting": "book_a_meeting",
        "end_interaction": "end_interaction",
    }
)

# Edge from gather_information (which might have errors) to generate_response
workflow.add_edge("book_a_meeting", "generate_response")
workflow.add_edge("gather_information", "generate_response")
workflow.add_edge("generate_response", "send_response")

def decide_after_send(state: ConversationState) -> str:
    """Decides the next step after sending a response."""
    print("---DECISION: After Sending Response---")
    intent = state.get("classified_intent")
    if state.get("error_message"):
        print("Decision: Error occurred, ending interaction.")
        return "end_interaction"
    if intent in [llm_service.INTENT_NOT_INTERESTED_BUYING, llm_service.INTENT_INTERESTED_SELLING_TO_US]:
        print(f"Decision: Definitive intent '{intent}' handled. Ending interaction.")
        return "end_interaction"
    print("Decision: Awaiting further input (next email).")
    return "await_further_input"

workflow.add_conditional_edges(
    "send_response",
    decide_after_send,
    {
        "await_further_input": "await_further_input",
        "end_interaction": "end_interaction"
    }
)

workflow.add_edge("await_further_input", END) # End of this processing cycle
workflow.add_edge("end_interaction", END)     # Explicit end state


# 5. Compile the graph
app = workflow.compile()
