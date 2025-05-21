from typing import TypedDict, List, Optional

class EmailConversationState(TypedDict):
    thread_id: Optional[str]
    last_updated: Optional[str]
    user_input: Optional[str]
    user_email: Optional[str]
    chat_history: List[str]
