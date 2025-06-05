# llm_service.py
from datetime import datetime
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.pydantic_v1 import BaseModel, Field
import config
from email_conversation_manager.types import POSSIBLE_INTENTS, AvailableSlot, ChatMessage, Intent

# Initialize the LangChain model
def get_llm_instance() -> Optional[ChatGoogleGenerativeAI]:
    """Returns an instance of the LangChain Gemini model."""
    if not config.GOOGLE_GEMINI_API_KEY:
        raise ValueError("Error: GOOGLE_GEMINI_API_KEY is not configured for LLM initialization.")
    try:
        model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.6,
            top_p=1,
            top_k=1,
            max_output_tokens=1024,
            google_api_key=config.GOOGLE_GEMINI_API_KEY
        )
        return model
    except Exception as e:
        print(f"Error initializing Gemini model: {e}")
        return None

llm_model = get_llm_instance() # Initialize once when module is loaded

def _safe_generate_content(intent_specific_instructions: str, history: list[ChatMessage] = None) -> Optional[str]:
    """Helper function to call LLM and handle common response patterns/errors."""
    if not llm_model:
        print("LLM model not initialized. Cannot generate content.")
        return None
    try:
            # Create system and human messages
        system_message = SystemMessage(content=SYSTEM_INSTRUCTIONS)
        intent_instructions = SystemMessage(content=intent_specific_instructions)
        chat_history = [system_message, intent_instructions]
        chat_history.extend([BaseMessage(role=x.role, content=x.content) for x in history if x.role != "System"])
        
        # Get response from model
        response = llm_model.invoke(chat_history)
        
        if response and response.content:
            return response.content.strip()
        
        print("Error: LLM did not return a valid response.")
        print(f"Full response object: {response}")
        return None
    except Exception as e:
        print(f"Error during LLM content generation: {e}")
        return None

# Define the intent classification model
class IntentClassification(BaseModel):
    """Model for classifying user intent."""
    intent: str = Field(
        description="The classified intent of the user's message",
        enum=POSSIBLE_INTENTS
    )
    confidence: float = Field(
        description="Confidence score of the classification (0-1)",
        ge=0,
        le=1
    )

def classify_user_intent(user_input: str, conversation_history: Optional[List[ChatMessage]] = None) -> str:
    """
    Classifies the user's intent based on their input and conversation history using LangChain's structured output.
    """
    if not llm_model:
        return Intent.UNSURE

    history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_history]) if conversation_history else "No previous conversation."

    # Create the system message
    system_message = SystemMessage(content="""You are an intent classification assistant.
Your task is to classify the user's intent based on their input and conversation history.
Choose the most appropriate intent from the predefined list.
Be precise and confident in your classification.""")

    # Create the human message with context
    human_message = HumanMessage(content=f"""Based on the LATEST USER INPUT and the CONVERSATION HISTORY (if any), classify the primary intent.

CONVERSATION HISTORY:
{history_str}

LATEST USER INPUT:
"{user_input}"

Available intents: {', '.join(POSSIBLE_INTENTS)}""")

    try:
        # Get structured output using the model
        structured_llm = llm_model.with_structured_output(IntentClassification)
        result = structured_llm.invoke([system_message, human_message])
        
        # Return the classified intent if confidence is high enough
        if result.confidence >= 0.7:
            return result.intent
        else:
            print(f"Low confidence ({result.confidence}) in intent classification. Defaulting to UNSURE.")
            return Intent.UNSURE
            
    except Exception as e:
        print(f"Error during intent classification: {e}")
        return Intent.UNSURE

# System instructions for the LLM
SYSTEM_INSTRUCTIONS = "You are Olli's Personal Assistant for OTL.fi. Always be professional, concise, and helpful."

BOOKING_TEMPLATES = {
    "en": "Hi {user_name},\n\nHere are the next available 30-minute time slots for a call with Olli (all times Helsinki/EEST):\n\n{slots}\n\nIf none of these work, you can suggest another time or use our booking link: {booking_link}\n\nLooking forward to your reply!\nOlli's Personal Assistant",
    "fi": "Hei {user_name},\n\nTässä seuraavat vapaat 30 minuutin ajat keskustelulle Ollin kanssa (ajat Helsinki/EEST):\n\n{slots}\n\nJos mikään näistä ei sovi, voit ehdottaa toista aikaa tai käyttää varauslinkkiä: {booking_link}\n\nOdotan vastaustasi!\nOllin henkilökohtainen assistentti"
}

# Define the booking response model
class BookingResponse(BaseModel):
    """Model for generating booking responses."""
    greeting: str = Field(description="Greeting with user's name")
    slots_intro: str = Field(description="Introduction to available slots")
    slots: List[str] = Field(description="List of available slots")
    fallback_option: str = Field(description="Text about suggesting another time or using booking link")
    booking_link: str = Field(description="The booking link")
    signoff: str = Field(description="Signoff message")

def get_booking_template(language: str, user_name: str, slots: list, booking_link: str) -> str:
    """Generates a booking response using tool calls for supported languages."""
    if language not in BOOKING_TEMPLATES:
        # For unsupported languages, use freeform response
        system_message = SystemMessage(content=f"""You are Olli's Personal Assistant for OTL.fi.
Generate a booking response in {language} using the provided information.
Be professional, concise, and helpful. Include a greeting, available slots, and a signoff.
The response should be in {language}.""")

        human_message = HumanMessage(content=f"""Generate a booking response with the following information:
- User name: {user_name or 'there'}
- Available slots: {slots if slots else '(No available slots)'}
- Booking link: {booking_link}

The response should be in {language} and include:
1. A greeting with the user's name
2. Introduction to available slots
3. List of available slots
4. Option to suggest another time or use the booking link
5. A professional signoff""")

        try:
            response = llm_model.invoke([system_message, human_message])
            if response and response.content:
                return response.content.strip()
        except Exception as e:
            print(f"Error generating freeform booking response: {e}")
            # Fallback to English template and translate
            template = BOOKING_TEMPLATES["en"]
            slots_str = "\n".join(f"- {slot}" for slot in slots) if slots else "(No available slots)"
            response = template.format(user_name=user_name or "there", slots=slots_str, booking_link=booking_link)
            return translate_text(response, language)

    # For supported languages, use the template
    template = BOOKING_TEMPLATES[language]
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
    conversation_history: list[ChatMessage],
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

    if intent == Intent.REQUEST_BOOKING:
        slot_list = [slot.get('time') if isinstance(slot, dict) else slot for slot in (available_slots or [])]
        print(f"[DEBUG] slot_list for booking: {slot_list}")
        booking_msg = get_booking_template(language, user_name, slot_list, booking_link)
        print(f"[DEBUG] booking_msg: {booking_msg}")
        if user_language not in BOOKING_TEMPLATES:
            booking_msg = translate_text(booking_msg, user_language)
        return booking_msg

    elif intent == Intent.QUESTION_SERVICES:
        slot_list = [slot.get('time') if isinstance(slot, dict) else slot for slot in (available_slots or [])]
        booking_msg = get_booking_template(language, user_name, slot_list, booking_link)

        prompt = f"""Provide a concise and helpful answer based on this information: {website_info}. Reply in {user_language if user_language else 'English'}.
Include booking template into the answer, translate it if needed.

BOOKING TEMPLATE:
{booking_msg}"""


    elif intent == Intent.GREETING:
        prompt =  f"The user sent a greeting. Respond politely and greet the user {user_name} Ask how you can help them today. Reply in {user_language if user_language else 'English'}."

    elif intent == Intent.PROVIDE_INFO:
        prompt = f"The user has provided some information: '{user_input}'. Acknowledge receipt of the information. If this completes a previous request from you (e.g. asking for their email or name), confirm that. Decide the next natural step, which might be to proceed with a booking if that was the prior intent, or ask if there's anything else you can help with. Reply in {user_language if user_language else 'English'}."

    elif intent == Intent.FOLLOW_UP:
        prompt = f"The user is following up: '{user_input}'. Check the conversation history to understand the context. Respond appropriately to their follow-up. If it's about a booking, re-iterate options or check status if possible (currently not possible). Reply in {user_language if user_language else 'English'}."

    elif intent == Intent.NOT_INTERESTED_BUYING:
        prompt = f"The user has indicated they are not interested in buying OTL.fi's services. Respond politely, thank them for their time, and perhaps mention they can reach out in the future if their needs change. Do not push for a booking. Reply in {user_language if user_language else 'English'}."

    elif intent == Intent.INTERESTED_SELLING_TO_US:
        prompt = f"The user seems interested in SELLING their products/services TO OTL.fi. Politely inform them that OTL.fi is not currently looking to procure such services/products. Thank them for their interest. Do NOT offer to book a call for this intent. Reply in {user_language if user_language else 'English'}."

    elif intent == Intent.UNSURE:
        prompt = f"The user's intent is unclear from their message: '{user_input}'. Politely ask for clarification on how you can help them. You can also offer the booking link ({booking_link}) if they'd like to discuss their needs with Olli. Reply in {user_language if user_language else 'English'}."

    else:
        prompt = f"The user's intent was classified as '{intent}', but no specific response guidance is available. Use your best judgment to respond to '{user_input}' based on the conversation history and general knowledge. If in doubt, offer to book a call: {booking_link}. Reply in {user_language if user_language else 'English'}."

    return _safe_generate_content(prompt, conversation_history)

class SlotSelection(BaseModel):
    """Model for selecting and booking a meeting slot."""
    selected_slot: Optional[datetime] = Field(
        description="The selected slot from the available slots",
        default=None
    )
    confidence: float = Field(
        description="Confidence score of the selection (0-1)",
        ge=0,
        le=1
    )

def validate_slot(result: SlotSelection, available_slots: list[AvailableSlot]) -> tuple[bool, str]:
    """Validates that the selected slot matches one from the available slots."""
    # Check if result is a SlotSelection instance
    if not isinstance(result, SlotSelection):
        return False, "Invalid result type: expected SlotSelection"
    
    # Check if result has required fields with correct types
    if not isinstance(result.selected_slot, datetime):
        return False, "Selected slot must be a datetime object"
    
    if not isinstance(result.confidence, float):
        return False, "Confidence must be a float value"
    
    if not 0 <= result.confidence <= 1:
        return False, "Confidence must be between 0 and 1"
    
    if not result.selected_slot:
        return False, "No slot was selected"
        
    # Convert available slots to datetime objects for comparison
    available_datetimes = []
    for slot in available_slots:
        if isinstance(slot, dict) and 'iso' in slot:
            try:
                available_datetimes.append(datetime.fromisoformat(slot['iso']))
            except ValueError:
                continue
        elif isinstance(slot, str):
            try:
                available_datetimes.append(datetime.fromisoformat(slot))
            except ValueError:
                continue
    
    # Check if selected slot matches any available slot
    for available_dt in available_datetimes:
        if result.selected_slot == available_dt:
            return True, ""
            
    return False, f"Selected slot {result.selected_slot} does not match any available slot"

def parse_booked_slot(
    user_input: str, 
    available_slots: list[AvailableSlot], 
    conversation_history: List[ChatMessage],
    max_retries: int = 3
) -> SlotSelection:
    """Parses the booked slot from the user's input and attempts to book it directly."""
    if not available_slots:
        return SlotSelection(selected_slot=None, confidence=0.0)
    
    now = datetime.now()
    last_error = None
    retry_count = 0

    # available_slots is a list of dicts with 'time' and 'iso' keys
    slot_list = [slot['time'] if isinstance(slot, dict) and 'time' in slot else str(slot) for slot in available_slots]
    slot_list_str = '\n'.join(f"- {slot}" for slot in slot_list)
    
    # Convert conversation history to string format
    conversation_history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_history]) if conversation_history else "No previous conversation."
    
    while retry_count < max_retries:
        system_message = SystemMessage(content="""You are an assistant that helps book meeting slots.
Your task is to select the exact slot string from the available slots that the user wants to book.
If the user says 'first', 'second', 'third', or gives a time, match to the correct slot.
Be precise and confident in your selection.
IMPORTANT: You must select a slot that exactly matches one from the available slots list.
If your selection is invalid, you will be given feedback and must try again.
                                   
date and time of the current moment: {now}""")
            
        human_message = HumanMessage(content=f"""The user has replied: '{user_input}'
Here are the available slots (each is a string):
{slot_list_str}

{last_error if last_error else ''}

Based on the user's message and the conversation history, select the exact slot string from the list above that the user wants to book.
You MUST select a slot that exactly matches one from the available slots list.
Conversation history:
{conversation_history_str}""")

        try:
            # Get structured output using the model
            structured_llm = llm_model.with_structured_output(SlotSelection)
            result = structured_llm.invoke([system_message, human_message])
            
            # Validate the selected slot
            is_valid, error_message = validate_slot(result, available_slots)
            
            if is_valid and result.confidence >= 0.7:
                return result
            
            last_error = f"Previous attempt failed: {error_message}. Please try again with a valid slot from the list."
            retry_count += 1
            
        except Exception as e:
            print(f"Error during slot selection and booking: {e}")
            last_error = f"An error occurred: {str(e)}. Please try again."
            retry_count += 1
    
    # If we've exhausted all retries, return failure
    print(f"Failed to get valid slot selection after {max_retries} attempts. Last error: {last_error}")
    return SlotSelection(selected_slot=None, confidence=0.0)

def generate_meeting_description(user_input: str, conversation_history: list[ChatMessage], user_language: str = None) -> str:
    """
    Generates a concise description of the user's intent and request, suitable for meeting description.
    """

    # Convert conversation history to a string
    conversation_history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_history])

    if not llm_model:
        return user_input[:200]  # fallback: just truncate the user input
    prompt = (
        f"You are an assistant that summarizes meeting requests for the organizer. "
        f"Given the user's latest message and the conversation history, generate a concise description (1-2 sentences) "
        f"explaining the main reason for the meeting. "
        f"Reply in {'Finnish' if user_language in ['fi', 'fi-fi'] else 'English'}.\n\n"
        f"CONVERSATION HISTORY:\n{conversation_history_str}\n\n"
        f"LATEST USER INPUT:\n{user_input}\n\n"
        f"Summary:"
    )
    summary = _safe_generate_content(prompt)
    return summary.strip() if summary else user_input[:200]