from datetime import datetime
from enum import StrEnum, auto, Enum
from typing import List, Optional

from pydantic import BaseModel

class Intent(StrEnum):
    """
    Enum representing possible intents in email conversations.
    Use these values for the classified_intent field in EmailConversationState.
    
    Example usage:
        state = EmailConversationState()
        state.classified_intent = Intent.REQUEST_BOOKING
    """
    REQUEST_BOOKING = auto()
    BOOK_A_MEETING = auto()
    GREETING = auto()
    PROVIDE_INFO = auto() # User provides requested info like name/email
    QUESTION_SERVICES = auto() # Specific questions about services
    FOLLOW_UP = auto() # User is following up on a previous conversation
    NOT_INTERESTED_BUYING = auto() # User explicitly states they are not interested in buying
    INTERESTED_SELLING_TO_US = auto() # User wants to sell something to OTL.fi
    UNSURE = auto() # Intent is not clear


# List of all possible intent values as strings
POSSIBLE_INTENTS = [intent.value for intent in Intent]

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatMessage(BaseModel):
    role: MessageRole
    content: str


class AvailableSlot(BaseModel):
    time: str  # Formatted string for user display
    iso: str   # ISO8601 string for API booking

class EmailConversationState(BaseModel):
    # Saved to database
    thread_id: str  # Gmail's thread ID for the conversation
    user_email: str
    user_name: str
    last_updated: Optional[datetime] = None
    previous_chat_history: List[ChatMessage] = []
    appended_chat_history: List[ChatMessage] = [] # These are combined with previous_chat_history to form the chat_history

    # Not saved to database
    user_input: Optional[str] = None
    classified_intent: Optional[Intent] = None  # Use Intent enum values, e.g., Intent.REQUEST_BOOKING
    available_slots: Optional[List[AvailableSlot]] = None
    booked_slot: Optional[AvailableSlot] = None
    generated_response: Optional[str] = None
    error_message: Optional[str] = None
    booking_link: Optional[str] = None      # Can be pre-set or generated
    event_type_slug: Optional[str] = None   # To help generate booking_link or fetch slots
    user_language: Optional[str] = None  # e.g., 'en', 'fi', 'sv' 

class EmailConversationDTO(BaseModel):
    thread_id: str
    user_email: str
    user_name: str
    last_updated: datetime
    available_slots: Optional[List[AvailableSlot]] = None
    booked_slot: Optional[AvailableSlot] = None
    chat_history: List[ChatMessage]

