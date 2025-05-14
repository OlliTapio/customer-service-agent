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
MODEL_NAME = "gemini-1.5-flash-latest" # Updated to a generally good model
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

def get_llm_instance():
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
INTENT_GREETING = "GREETING"
INTENT_GENERAL_QUERY = "GENERAL_QUERY"
INTENT_PROVIDE_INFO = "PROVIDE_INFO" # User provides requested info like name/email
INTENT_QUESTION_SERVICES = "QUESTION_SERVICES" # Specific questions about services
INTENT_FOLLOW_UP = "FOLLOW_UP" # User is following up on a previous conversation
INTENT_NOT_INTERESTED_BUYING = "NOT_INTERESTED_BUYING" # User explicitly states they are not interested in buying
INTENT_INTERESTED_SELLING_TO_US = "INTERESTED_SELLING_TO_US" # User wants to sell something to OTL.fi
INTENT_UNSURE = "UNSURE" # Intent is not clear

POSSIBLE_INTENTS = [
    INTENT_REQUEST_BOOKING, INTENT_GREETING, INTENT_GENERAL_QUERY, INTENT_PROVIDE_INFO,
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

def generate_contextual_response(
    intent: str,
    user_input: str,
    conversation_history: List[str],
    user_name: Optional[str] = None,
    available_slots: Optional[List[Dict[str, Any]]] = None,
    booking_link: Optional[str] = None,
    event_type_slug: Optional[str] = None, # Added for constructing booking link if needed
    website_info: str = "OTL.fi specializes in innovative tech solutions. For detailed discussions, a call is recommended."
) -> str:
    """
    Generates an email response based on the classified intent and conversation context.
    """
    if not llm_model:
        return "I apologize, our AI assistant is currently unavailable. Please try again later."

    if not booking_link and event_type_slug and config.CAL_COM_USERNAME: # Construct booking link if parts are available
        booking_link = f"https://cal.com/{config.CAL_COM_USERNAME}/{event_type_slug}"


    prompt_parts = [
        f"You are a friendly and professional AI assistant for OTL.fi, a company offering innovative tech solutions.",
        f"Your name is 'Olli\\'s Personal Assistant'. Sign off all emails with this name.",
        "Your primary goal is to be helpful and, when appropriate, guide users to book a 30-minute introduction call with Olli from OTL.fi.",
        "Address the user by name if known. The user's name is {user_name if user_name else 'there'}."
    ]

    history_str = "\\n".join(conversation_history) # Assumes history includes "User: ..." and "System: ..."

    prompt_parts.append(f"\\n--- Conversation History ---")
    prompt_parts.append(history_str)
    prompt_parts.append(f"--- End Conversation History ---\\n")
    prompt_parts.append(f"LATEST USER INPUT: \\\"{user_input}\\\"")

    if intent == INTENT_REQUEST_BOOKING:
        prompt_parts.append(f"The user wants to book a meeting.")
        if available_slots:
            formatted_slots = []
            for i, slot in enumerate(available_slots[:5]): # Show max 5 slots
                # Assuming slot format is {'time': 'YYYY-MM-DDTHH:MM:SSZ'}
                # Convert to a more human-readable format if needed, or pass as is if LLM handles it.
                # For simplicity, passing raw for now. LLM should be instructed on format.
                formatted_slots.append(f"  - {slot['time']} (UTC)")
            slots_text = "\\n".join(formatted_slots)
            prompt_parts.append(f"Here are some available time slots for the 30-minute meeting (times are in UTC):\\n{slots_text}")
            prompt_parts.append(f"Please ask the user to confirm one of these slots or suggest another time if these don't work.")
            prompt_parts.append(f"If they confirm, you can tell them you'll send a calendar invite shortly (though you won't actually send it, Olli will).")
        elif booking_link:
            prompt_parts.append(f"No specific slots were pre-fetched or they were not suitable. Guide them to book using this link: {booking_link}")
        else:
            prompt_parts.append("It seems there was an issue fetching available slots and no general booking link is available. Apologize and suggest they try again later or contact OTL.fi directly for booking.")
    
    elif intent == INTENT_GREETING:
        prompt_parts.append("The user sent a greeting. Respond politely and ask how you can help them today. If appropriate, subtly mention they can book a call for detailed discussions about OTL.fi services.")

    elif intent == INTENT_GENERAL_QUERY or intent == INTENT_QUESTION_SERVICES:
        prompt_parts.append(f"The user has a general query or a specific question about services: \'{user_input}\'.")
        prompt_parts.append(f"Provide a concise and helpful answer if possible based on general knowledge and this information: {website_info}")
        prompt_parts.append(f"If the question is complex or requires specific details, politely state that it's best discussed on a call and offer the booking link: {booking_link if booking_link else 'visit our website to book a call.'}")

    elif intent == INTENT_PROVIDE_INFO:
        prompt_parts.append(f"The user has provided some information: \'{user_input}\'. Acknowledge receipt of the information. If this completes a previous request from you (e.g. asking for their email or name), confirm that. Decide the next natural step, which might be to proceed with a booking if that was the prior intent, or ask if there's anything else you can help with.")

    elif intent == INTENT_FOLLOW_UP:
        prompt_parts.append(f"The user is following up: \'{user_input}\'. Check the conversation history to understand the context. Respond appropriately to their follow-up. If it's about a booking, re-iterate options or check status if possible (currently not possible).")

    elif intent == INTENT_NOT_INTERESTED_BUYING:
        prompt_parts.append(f"The user has indicated they are not interested in buying OTL.fi's services. Respond politely, thank them for their time, and perhaps mention they can reach out in the future if their needs change. Do not push for a booking.")

    elif intent == INTENT_INTERESTED_SELLING_TO_US:
        prompt_parts.append(f"The user seems interested in SELLING their products/services TO OTL.fi. Politely inform them that OTL.fi is not currently looking to procure such services/products. Thank them for their interest.")
        prompt_parts.append(f"Do NOT offer to book a call for this intent.")

    elif intent == INTENT_UNSURE:
        prompt_parts.append(f"The user's intent is unclear from their message: \'{user_input}\'. Politely ask for clarification on how you can help them. You can also offer the booking link ({booking_link}) if they'd like to discuss their needs with Olli.")
    
    else: # Fallback for any unhandled classified intents
        prompt_parts.append(f"The user's intent was classified as \'{intent}\', but no specific response guidance is available. Use your best judgment to respond to \'{user_input}\' based on the conversation history and general knowledge. If in doubt, offer to book a call: {booking_link}.")

    prompt_parts.append("\\nInstructions for the AI:")
    prompt_parts.append("- Generate ONLY the body of the email reply. Do NOT include a subject line.")
    prompt_parts.append("- Be concise, friendly, and professional.")
    prompt_parts.append("- If a booking link is provided and relevant, make sure to include it.")
    prompt_parts.append(f"- Sign off as 'Olli\\'s Personal Assistant'.")
    prompt_parts.append("\\nEmail Body to Generate:")
    
    final_prompt = "\\n".join(prompt_parts)
    # print(f"\\n--- LLM PROMPT for \'{intent}\' ---")
    # print(final_prompt)
    # print("--- END LLM PROMPT ---\\n")

    response_text = _safe_generate_content(final_prompt)

    if response_text == "BLOCKED_CONTENT":
        return f"I apologize, but I'm unable to respond to this specific query due to content safety guidelines. Please rephrase or book a call with us (link: {booking_link if booking_link else 'on our website'}) for assistance."
    
    return response_text if response_text else "I apologize, I encountered an issue generating a response. Please try again or contact us directly."


# Example Usage (for direct testing of this module)
if __name__ == '__main__':
    if not config.GOOGLE_GEMINI_API_KEY or not llm_model:
        print("Cannot run llm_service.py example: API key not set or model failed to initialize.")
    else:
        print("--- Testing Intent Classification ---")
        test_inputs = [
            "Hi there, can I book a meeting?",
            "Hello!",
            "What services do you offer?",
            "My name is Bob.",
            "I'm not interested, thanks.",
            "We want to sell you our amazing CRM solution!",
            "Not sure what I need yet."
        ]
        for inp in test_inputs:
            intent = classify_user_intent(user_input=inp)
            print(f"Input: \"{inp}\" -> Classified Intent: {intent}")

        print("\\n--- Testing Contextual Response Generation ---")
        
        # Test 1: Request Booking with slots
        print("\\nTest 1: Request Booking with slots")
        history1 = ["User: I want to book a time.", "System: Classified intent as REQUEST_BOOKING", "System: Fetched available slots: [{'time': '2025-07-01T10:00:00Z'}, {'time': '2025-07-01T11:00:00Z'}]"]
        response1 = generate_contextual_response(
            intent=INTENT_REQUEST_BOOKING,
            user_input="Yes, those times look good.",
            conversation_history=history1,
            user_name="Alice",
            available_slots=[{'time': '2025-07-01T10:00:00Z'}, {'time': '2025-07-01T11:00:00Z'}],
            booking_link="https://cal.com/otl-user/30min"
        )
        print(f"Generated Response:\\n{response1}")

        # Test 2: General Query
        print("\\nTest 2: General Query")
        history2 = ["User: What can you do for me?", "System: Classified intent as GENERAL_QUERY"]
        response2 = generate_contextual_response(
            intent=INTENT_GENERAL_QUERY,
            user_input="Tell me about your cloud solutions.",
            conversation_history=history2,
            user_name="Bob",
            booking_link="https://cal.com/otl-user/30min",
            website_info="OTL.fi offers scalable cloud infrastructure and migration services."
        )
        print(f"Generated Response:\\n{response2}")

        # Test 3: User wants to sell to us
        print("\\nTest 3: User wants to sell to us")
        history3 = ["User: I have a product that OTL.fi would love!", "System: Classified intent as INTERESTED_SELLING_TO_US"]
        response3 = generate_contextual_response(
            intent=INTENT_INTERESTED_SELLING_TO_US,
            user_input="It's a revolutionary new paperclip design.",
            conversation_history=history3,
            user_name="Paperclip Salesman",
            booking_link="https://cal.com/otl-user/30min"
        )
        print(f"Generated Response:\\n{response3}")
        
        # Test 4: Greeting
        print("\\nTest 4: Greeting")
        history4 = ["User: Hello", "System: Classified intent as GREETING"]
        response4 = generate_contextual_response(
            intent=INTENT_GREETING,
            user_input="Hi",
            conversation_history=history4,
            user_name=None,
            booking_link="https://cal.com/otl-user/30min"
        )
        print(f"Generated Response:\\n{response4}") 