# llm_service.py
import google.generativeai as genai
import config
from typing import List, Optional, Dict, Any

# Configure the Gemini API key
if config.GOOGLE_GEMINI_API_KEY:
    genai.configure(api_key=config.GOOGLE_GEMINI_API_KEY)
else:
    print("Error: GOOGLE_GEMINI_API_KEY is not configured. LLM service will not work.")
    # You might want to raise an exception here or handle this more gracefully
    # depending on how critical the LLM service is for the application to start.

# Initialize the Generative Model
# You can choose different models, e.g., 'gemini-pro', 'gemini-1.0-pro', 'gemini-1.5-flash-latest', etc.
# For chat-like interactions, especially if you need to maintain history, 
# starting a chat session (model.start_chat()) is often better.
# For simple prompt-response, generate_content is fine.
MODEL_NAME = "gemini-2.0-flash" 
# Set up safety settings if needed. By default, they are quite strict.
# More info: https://ai.google.dev/docs/safety_setting_gemini
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

GENERATION_CONFIG = {
  "temperature": 0.6, # Slightly lower for more predictable classification and response
  "top_p": 1,
  "top_k": 1,
  "max_output_tokens": 1024, # Reduced slightly, assuming responses are concise
  "response_mime_type": "text/plain", # Explicitly ask for plain text
}

def get_llm_instance() -> Optional[Any]:
    """Returns an instance of the Gemini model."""
    if not config.GOOGLE_GEMINI_API_KEY:
        print("LLM model cannot be initialized: GOOGLE_GEMINI_API_KEY is not set.")
        return None
    try:
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config=GENERATION_CONFIG,
            safety_settings=SAFETY_SETTINGS
        )
        return model
    except Exception as e:
        print(f"Error initializing Gemini model: {e}")
        return None

llm_model = get_llm_instance() # Initialize once when module is loaded

# Define standard intent labels
INTENT_REQUEST_BOOKING = "REQUEST_BOOKING"
INTENT_BOOK_A_MEETING = "BOOK_A_MEETING"
INTENT_GREETING = "GREETING"
INTENT_PROVIDE_INFO = "PROVIDE_INFO" # User provides requested info like name/email
INTENT_QUESTION_SERVICES = "QUESTION_SERVICES" # Specific questions about services
INTENT_FOLLOW_UP = "FOLLOW_UP" # User is following up on a previous conversation
INTENT_NOT_INTERESTED_BUYING = "NOT_INTERESTED_BUYING" # User explicitly states they are not interested in buying
INTENT_INTERESTED_SELLING_TO_US = "INTERESTED_SELLING_TO_US" # User wants to sell something to OTL.fi
INTENT_UNSURE = "UNSURE" # Intent is not clear

POSSIBLE_INTENTS = [
    INTENT_REQUEST_BOOKING, INTENT_BOOK_A_MEETING, INTENT_GREETING,
    INTENT_PROVIDE_INFO,
    INTENT_QUESTION_SERVICES, INTENT_FOLLOW_UP, INTENT_NOT_INTERESTED_BUYING,
    INTENT_INTERESTED_SELLING_TO_US, INTENT_UNSURE
]

def _safe_generate_content(prompt: str) -> Optional[str]:
    """Helper function to call LLM and handle common response patterns/errors."""
    if not llm_model:
        print("LLM model not initialized. Cannot generate content.")
        return None
    try:
        response = llm_model.generate_content(prompt)
        if response and response.parts:
            first_part = response.parts[0]
            if hasattr(first_part, 'text'):
                return first_part.text.strip()
        elif response and response.text: # Fallback for simpler text attribute
             return response.text.strip()
        
        # Handle cases where the response might be empty due to blocking
        if response and response.prompt_feedback and response.prompt_feedback.block_reason:
            print(f"Prompt was blocked. Reason: {response.prompt_feedback.block_reason}")
            # For classification, returning UNSURE might be appropriate
            # For generation, a polite error message is better.
            return "BLOCKED_CONTENT" 
        
        print("Error: LLM did not return a valid response or response parts.")
        print(f"Full response object: {response}")
        return None
    except Exception as e:
        print(f"Error during LLM content generation: {e}")
        return None

def classify_user_intent(user_input: str, conversation_history: Optional[List[str]] = None) -> str:
    """
    Classifies the user's intent based on their input and conversation history.
    """
    if not llm_model:
        return INTENT_UNSURE

    history_str = "\\\\n".join(conversation_history) if conversation_history else "No previous conversation."

    # Constructing the prompt carefully to avoid f-string issues with escapes
    prompt = "You are an intent classification assistant.\\n"
    prompt += "Based on the LATEST USER INPUT and the CONVERSATION HISTORY (if any), classify the primary intent of the LATEST USER INPUT.\\n"
    prompt += "Choose ONLY ONE of the following intents:\\n"
    prompt += ", ".join(POSSIBLE_INTENTS) + "\\n\\n"
    prompt += "CONVERSATION HISTORY:\\n"
    prompt += history_str + "\\n\\n"
    prompt += "LATEST USER INPUT:\\n"
    prompt += f'"{user_input}"\\n\\n' # Use f-string only for the user_input part
    prompt += "INTENT:"

    classified_intent = _safe_generate_content(prompt)

    if classified_intent == "BLOCKED_CONTENT":
        return INTENT_UNSURE # If content is blocked, we can't classify
    if classified_intent and classified_intent in POSSIBLE_INTENTS:
        return classified_intent
    else:
        print(f"Warning: LLM returned an unknown or empty intent: \'{classified_intent}\'. Defaulting to UNSURE.")
        return INTENT_UNSURE

# System instructions for the LLM
SYSTEM_INSTRUCTIONS = "You are Olli's Personal Assistant for OTL.fi. Always be professional, concise, and helpful."

BOOKING_TEMPLATES = {
    "en": "Hi {user_name},\n\nHere are the next available 30-minute time slots for a call with Olli (all times Helsinki/EEST):\n\n{slots}\n\nIf none of these work, you can suggest another time or use our booking link: {booking_link}\n\nLooking forward to your reply!\nOlli's Personal Assistant",
    "fi": "Hei {user_name},\n\nTässä seuraavat vapaat 30 minuutin ajat keskustelulle Ollin kanssa (ajat Helsinki/EEST):\n\n{slots}\n\nJos mikään näistä ei sovi, voit ehdottaa toista aikaa tai käyttää varauslinkkiä: {booking_link}\n\nOdotan vastaustasi!\nOllin henkilökohtainen assistentti"
}


def get_booking_template(language: str, user_name: str, slots: list, booking_link: str) -> str:
    template = BOOKING_TEMPLATES.get(language, BOOKING_TEMPLATES["en"])
    slots_str = "\n".join(f"- {slot}" for slot in slots) if slots else "(No available slots)"
    return template.format(user_name=user_name or "there", slots=slots_str, booking_link=booking_link)


def translate_text(text: str, target_language: str) -> str:
    if target_language in BOOKING_TEMPLATES:
        return text  # Already in supported language
    prompt = f"{SYSTEM_INSTRUCTIONS}\nTranslate the following message to {target_language}. If not possible, return the original English.\n\n{text}"
    translated = _safe_generate_content(prompt)
    return translated or text


def generate_service_answer(user_input: str, website_info: str, user_language: str, conversation_history: list = None) -> str:
    history_str = "\n".join(conversation_history) if conversation_history else ""
    prompt = f"{SYSTEM_INSTRUCTIONS}\n" \
            f"Conversation history:\n{history_str}\n" \
            f"The user asked: '{user_input}'.\n" \
            f"Provide a concise and helpful answer based on this information: {website_info}. Reply in {user_language if user_language else 'English'}."
    return _safe_generate_content(prompt) or "I'm sorry, I couldn't generate an answer to your question."


def generate_greeting_response(user_name: str, user_language: str, conversation_history: list = None) -> str:
    history_str = "\n".join(conversation_history) if conversation_history else ""
    name_part = f" {user_name}," if user_name else ""
    prompt = f"{SYSTEM_INSTRUCTIONS}\n" \
            f"Conversation history:\n{history_str}\n" \
            f"The user sent a greeting. Respond politely and greet the user{name_part} Ask how you can help them today. Reply in {user_language if user_language else 'English'}."
    return _safe_generate_content(prompt) or f"Hello{name_part}! How can I help you today?"


def generate_contextual_response(
    intent: str,
    user_input: str,
    conversation_history: list,
    user_name: str = None,
    available_slots: list = None,
    booking_link: str = None,
    event_type_slug: str = None,
    website_info: str = "OTL.fi provides AI audit and implementation for companies interested in freeing time in their organisation from menial work. For detailed discussions, a call is recommended.",
    user_language: str = None
) -> str:
    """
    Generates an email response based on the classified intent and conversation context.
    """
    if not llm_model:
        return (
            "I apologize, our AI assistant is currently unavailable. "
            "Please try again later or contact us directly."
        )

    if not booking_link and event_type_slug and config.CAL_COM_USERNAME:
        booking_link = f"https://cal.com/{config.CAL_COM_USERNAME}/{event_type_slug}"

    language = user_language if user_language in BOOKING_TEMPLATES else "en"

    # DEBUG: Print available_slots
    print(f"[DEBUG] available_slots: {available_slots}")

    if intent == INTENT_REQUEST_BOOKING:
        slot_list = [slot.get('time') if isinstance(slot, dict) else slot for slot in (available_slots or [])]
        print(f"[DEBUG] slot_list for booking: {slot_list}")
        booking_msg = get_booking_template(language, user_name, slot_list, booking_link)
        print(f"[DEBUG] booking_msg: {booking_msg}")
        if user_language not in BOOKING_TEMPLATES:
            booking_msg = translate_text(booking_msg, user_language)
        return booking_msg

    elif intent == INTENT_QUESTION_SERVICES:
        answer = generate_service_answer(user_input, website_info, user_language, conversation_history)
        slot_list = [slot.get('time') if isinstance(slot, dict) else slot for slot in (available_slots or [])]
        print(f"[DEBUG] slot_list for service question: {slot_list}")
        booking_msg = get_booking_template(language, user_name, slot_list, booking_link)
        print(f"[DEBUG] booking_msg: {booking_msg}")
        if user_language not in BOOKING_TEMPLATES:
            booking_msg = translate_text(booking_msg, user_language)
        return f"{answer}\n\n{booking_msg}"

    elif intent == INTENT_GREETING:
        return generate_greeting_response(user_name, user_language, conversation_history)

    elif intent == INTENT_PROVIDE_INFO:
        prompt = f"The user has provided some information: '{user_input}'. Acknowledge receipt of the information. If this completes a previous request from you (e.g. asking for their email or name), confirm that. Decide the next natural step, which might be to proceed with a booking if that was the prior intent, or ask if there's anything else you can help with. Reply in {user_language if user_language else 'English'}."

    elif intent == INTENT_FOLLOW_UP:
        prompt = f"The user is following up: '{user_input}'. Check the conversation history to understand the context. Respond appropriately to their follow-up. If it's about a booking, re-iterate options or check status if possible (currently not possible). Reply in {user_language if user_language else 'English'}."

    elif intent == INTENT_NOT_INTERESTED_BUYING:
        prompt = f"The user has indicated they are not interested in buying OTL.fi's services. Respond politely, thank them for their time, and perhaps mention they can reach out in the future if their needs change. Do not push for a booking. Reply in {user_language if user_language else 'English'}."

    elif intent == INTENT_INTERESTED_SELLING_TO_US:
        prompt = f"The user seems interested in SELLING their products/services TO OTL.fi. Politely inform them that OTL.fi is not currently looking to procure such services/products. Thank them for their interest. Do NOT offer to book a call for this intent. Reply in {user_language if user_language else 'English'}."

    elif intent == INTENT_UNSURE:
        prompt = f"The user's intent is unclear from their message: '{user_input}'. Politely ask for clarification on how you can help them. You can also offer the booking link ({booking_link}) if they'd like to discuss their needs with Olli. Reply in {user_language if user_language else 'English'}."

    else:
        prompt = f"The user's intent was classified as '{intent}', but no specific response guidance is available. Use your best judgment to respond to '{user_input}' based on the conversation history and general knowledge. If in doubt, offer to book a call: {booking_link}. Reply in {user_language if user_language else 'English'}."

    return _safe_generate_content(f"{SYSTEM_INSTRUCTIONS}\n{prompt}")

def parse_booked_slot(user_input: str, available_slots: list, conversation_history: list) -> str:
    """Parses the booked slot from the user's input using the LLM.
    Returns the formatted string (slot['time']) for matching in conversation_manager.py.
    The ISO string (slot['iso']) is used for the API call after matching."""
    # available_slots is a list of dicts with 'time' and 'iso' keys
    slot_list = [slot['time'] if isinstance(slot, dict) and 'time' in slot else str(slot) for slot in available_slots]
    slot_list_str = '\n'.join(f"- {slot}" for slot in slot_list)
    prompt = f"{SYSTEM_INSTRUCTIONS}\n" \
            f"You are an assistant that helps book meeting slots. The user has replied: '{user_input}'.\n" \
            f"Here are the available slots (each is a string):\n{slot_list_str}\n" \
            f"Based on the user's message and the conversation history, select the exact slot string from the list above that the user wants to book.\n" \
            f"If the user says 'first', 'second', 'third', or gives a time, match to the correct slot.\n" \
            f"Respond with ONLY the exact slot string (must match one of the above), or an empty string if no match. Do not add any explanation or extra text.\n" \
            f"Conversation history:\n{conversation_history}\n"
    return _safe_generate_content(prompt)