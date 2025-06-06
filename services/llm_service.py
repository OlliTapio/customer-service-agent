# llm_service.py
from datetime import datetime, timezone
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from pydantic import BaseModel, Field
import config
from email_conversation_manager.types import POSSIBLE_INTENTS, AvailableSlot, ChatMessage, Intent, MessageRole

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
        
        # Convert ChatMessage to appropriate langchain message type
        if history:
            for msg in history:
                if msg.role == MessageRole.USER:
                    chat_history.append(HumanMessage(content=msg.content))
                elif msg.role == MessageRole.ASSISTANT:
                    chat_history.append(AIMessage(content=msg.content))
                elif msg.role == MessageRole.SYSTEM:
                    chat_history.append(SystemMessage(content=msg.content))
        
        # Ensure we have at least one human message
        if not any(isinstance(msg, HumanMessage) for msg in chat_history):
            chat_history.append(HumanMessage(content="Please provide a response."))
        
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
    "en": "Here are the next available 30-minute time slots for a call with Olli (all times Helsinki/EEST):\n\n{slots}\n\nIf none of these work, you can suggest another time or use our booking link: {booking_link}",
    "fi": "Tässä seuraavat vapaat 30 minuutin ajat keskustelulle Ollin kanssa (ajat Helsinki/EEST):\n\n{slots}\n\nJos mikään näistä ei sovi, voit ehdottaa toista aikaa tai käyttää varauslinkkiä: {booking_link}"
}

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

def _format_prompt(
    main_instructions: list[str],
    user_language: str = None,
    user_name: str = None,
    include_template: bool = False,
    template_content: str = None
) -> str:
    """
    Helper function to format prompts with consistent structure.
    
    Args:
        main_instructions: List of main instruction points
        user_language: User's preferred language
        user_name: User's name if available
        include_template: Whether to include a template in the response
        template_content: The template content to include if include_template is True
    """
    prompt_parts = ["Your response should:"]
    
    # Add main instructions
    for i, instruction in enumerate(main_instructions, 1):
        prompt_parts.append(f"{i}. {instruction}")
    
    # Add template if needed
    if include_template and template_content:
        prompt_parts.append(f"\nTEMPLATE TO INCLUDE:\n{template_content}")
    
    # Add common instructions
    prompt_parts.append(f"\nAdditional requirements:")
    prompt_parts.append(f"1. Be in {user_language if user_language else 'English'}")
    prompt_parts.append(f"2. Start with a greeting using the user's name if available")
    prompt_parts.append(f"3. End with an email signature. You are Olli's Personal Assistant")
    
    return "\n".join(prompt_parts)

def generate_contextual_response(
    intent: str,
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

    if intent == Intent.REQUEST_BOOKING:
        # For booking requests, just use the template directly
        slots_str = "\n".join(f"- {slot.time}" for slot in available_slots) if available_slots else "(No available slots)"
        booking_msg = BOOKING_TEMPLATES[language].format(
            slots=slots_str,
            booking_link=booking_link
        )
        if user_language not in BOOKING_TEMPLATES:
            booking_msg = translate_text(booking_msg, user_language)
        
        # Format the complete response with greeting and signature
        greeting = f"Hi {user_name}," if user_name else "Hi there,"
        return f"{greeting}\n\n{booking_msg}\n\nLooking forward to your reply!\nOlli's Personal Assistant"

    elif intent == Intent.QUESTION_SERVICES:
        # Format slots properly
        slots_str = "\n".join(f"- {slot.time}" for slot in available_slots) if available_slots else "(No available slots)"
        booking_msg = BOOKING_TEMPLATES[language].format(
            slots=slots_str,
            booking_link=booking_link
        )
        if user_language not in BOOKING_TEMPLATES:
            booking_msg = translate_text(booking_msg, user_language)

        main_instructions = [
            "Briefly explain what OTL.fi does",
            "Include the booking template exactly as provided",
            "Be professional and helpful"
        ]
        
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name,
            include_template=True,
            template_content=booking_msg
        )

        return _safe_generate_content(prompt, conversation_history)

    elif intent == Intent.GREETING:
        main_instructions = [
            "Respond politely and greet the user",
            "Ask how you can help them today"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

    elif intent == Intent.PROVIDE_INFO:
        main_instructions = [
            "Acknowledge receipt of the information",
            "If this completes a previous request (e.g. asking for their email or name), confirm that",
            "Decide the next natural step, which might be to proceed with a booking if that was the prior intent, or ask if there's anything else you can help with"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

    elif intent == Intent.FOLLOW_UP:
        main_instructions = [
            "Check the conversation history to understand the context",
            "Respond appropriately to their follow-up",
            "If it's about a booking, re-iterate options or check status if possible (currently not possible)"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

    elif intent == Intent.NOT_INTERESTED_BUYING:
        main_instructions = [
            "The user has indicated they are not interested in buying OTL.fi's services",
            "Respond politely and thank them for their time",
            "Mention they can reach out in the future if their needs change",
            "Do not push for a booking"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

    elif intent == Intent.INTERESTED_SELLING_TO_US:
        main_instructions = [
            "The user seems interested in SELLING their products/services TO OTL.fi",
            "Acknowledge their specific service/product offering (e.g., SEO, marketing, etc.)",
            "Politely inform them that OTL.fi is not currently looking to procure such services/products",
            "Thank them for their interest",
            "Do NOT offer to book a call for this intent",
            "Keep the response professional but personal, acknowledging their specific business and offering"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

    elif intent == Intent.UNSURE:
        main_instructions = [
            "The user's intent is unclear from their latest message",
            "Politely ask for clarification on how you can help them",
            f"You can also offer the booking link ({booking_link}) if they'd like to discuss their needs with Olli"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

    elif intent == Intent.BOOK_A_MEETING:
        main_instructions = [
            "The user wanted to book a meeting",
            "We encountered an error while booking the meeting",
            f"Provide the user with the booking link ({booking_link}) and ask if they'd like to try again"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

    else:
        main_instructions = [
            f"The user's intent was classified as '{intent}', but no specific response guidance is available",
            "Use your best judgment to respond to the latest message based on the conversation history and general knowledge",
            f"If in doubt, offer to book a call: {booking_link}"
        ]
        prompt = _format_prompt(
            main_instructions=main_instructions,
            user_language=user_language,
            user_name=user_name
        )

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
    
    if isinstance(result.selected_slot, str):
        result.selected_slot = datetime.fromisoformat(result.selected_slot)

    # Check if result has required fields with correct types
    if not isinstance(result.selected_slot, datetime):
        return False, "Selected slot must be a datetime object"
    
    if not isinstance(result.confidence, float):
        return False, "Confidence must be a float value"
    
    if not 0 <= result.confidence <= 1:
        return False, "Confidence must be between 0 and 1"
    
    if not result.selected_slot:
        return False, "No slot was selected"
        
    # Convert selected slot to UTC
    selected_utc = result.selected_slot.astimezone(timezone.utc)
    
    # Check if selected slot matches any available slot
    for slot in available_slots:
        # Convert available slot to UTC
        available_dt = datetime.fromisoformat(slot.iso)
        available_utc = available_dt.astimezone(timezone.utc)
        
        # Calculate time difference
        time_diff = abs((selected_utc - available_utc).total_seconds())
        if time_diff < 1:  # Less than 1 second difference
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
    retry_count = 0

    # available_slots is a list of dicts with 'time' and 'iso' keys
    slot_list_str = '\n'.join(f"- {slot.iso} - {slot.time}" for slot in available_slots)
    
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
Here are the available slots (each is a string) as time and iso format. Use the ISO format:
{slot_list_str}

Based on the user's message and the conversation history, select the exact slot string from the list above that the user wants to book.
You MUST select a slot that exactly matches one from the available slots list.
Conversation history:
{conversation_history_str}""")

        try:
            # Get structured output using the model
            ai_chat = [system_message, human_message]
            structured_llm = llm_model.with_structured_output(SlotSelection)
            result = structured_llm.invoke(ai_chat)
            
            # Validate the selected slot
            is_valid, error_message = validate_slot(result, available_slots)
            
            if is_valid and result.confidence >= 0.7:
                return result
            
            last_error = f"Previous attempt failed: {error_message}. Please try again with a valid slot from the list."
            ai_chat.append(AIMessage(content=last_error))
            retry_count += 1
            
        except Exception as e:
            print(f"Error during slot selection and booking: {e}")
            last_error = f"An error occurred: {str(e)}. Please try again."
            ai_chat.append(AIMessage(content=last_error))
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