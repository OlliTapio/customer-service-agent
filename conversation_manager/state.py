from typing import TypedDict, List, Optional

class AvailableSlot(TypedDict):
    time: str  # Formatted string for user display
    iso: str   # ISO8601 string for API booking

class ConversationState(TypedDict):
    thread_id: Optional[str]  # Gmail's thread ID for the conversation
    last_updated: Optional[str]    # ISO timestamp of last update
    user_input: Optional[str]
    user_email: Optional[str]
    user_name: Optional[str]
    interaction_history: List[str]
    classified_intent: Optional[str]
    available_slots: Optional[List[AvailableSlot]]
    booked_slot: Optional[str]
    generated_response: Optional[str]
    error_message: Optional[str]
    booking_link: Optional[str]      # Can be pre-set or generated
    event_type_slug: Optional[str]   # To help generate booking_link or fetch slots
    user_language: Optional[str]  # e.g., 'en', 'fi', 'sv' 