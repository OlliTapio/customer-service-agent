from typing import List, Optional
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from assistant.assistant import Assistant
from assistant.database import ConversationDatabase
from assistant.types import ChatMessage
from services import gmail_service


class EmailConversationState(BaseModel):
    thread_id: Optional[str]
    last_updated: Optional[str]
    user_input: Optional[str]
    user_email: Optional[str]
    subject: Optional[str]
    message_body: Optional[str]
    chat_history: List[ChatMessage]
    new_chat_history: List[ChatMessage]
    assistant_response: Optional[str]
    assistant: Optional[Assistant] = None

conversation_database = ConversationDatabase()


def create_email_conversation_graph() -> StateGraph:
    """Creates and configures the conversation workflow graph."""
    workflow = StateGraph(EmailConversationState)

    # Add nodes
    workflow.add_node("message_received", message_received)
    workflow.add_node("handle_message", handle_message)
    workflow.add_node("send_response", send_response)
    workflow.add_node("save_state", save_state)
    # Set entry point
    workflow.set_entry_point("message_received")

    workflow.add_edge("message_received", "handle_message")
    workflow.add_edge("handle_message", "send_response")
    workflow.add_edge("send_response", "save_state")
    workflow.add_edge("save_state", END)

    return workflow.compile()


def message_received(state: EmailConversationState, thread_id: str, user_email: str, subject: str, message_body: str) -> str:
    """
    Checks if the conversation id already exists in the database and continues the conversation.
    Otherwise, starts a new conversation.
    """
    print("---NODE: Message Received---")

    state.thread_id = thread_id
    state.user_email = user_email
    state.subject = subject
    state.message_body = message_body

    # Fetch chat history with the thread id
    state.chat_history = conversation_database.get_or_create_conversation_history(state.thread_id, state.user_email)
    
    # Initialize the assistant with customer details
    state.assistant = Assistant(
        customer_email=state.user_email
    )
    
    return "handle_message"

def handle_message(state: EmailConversationState) -> str:
    """
    This function sends the message body to the LLM and gets a response.
    Uses the start conversation function if the history is empty. 
    Otherwise, uses the continue conversation function.
    """
    print("---NODE: Handle Message---")

    if not state.assistant:
        raise ValueError("Assistant not initialized")
    
    state.assistant_response, state.new_chat_history = state.assistant.handle_conversation(state.message_body, state.chat_history)
    
    return "send_response"

def send_response(state: EmailConversationState) -> str:
    """
    This function sends email response to the user.
    It adds greeting and signature to the message.
    """
    print("---NODE: Send Response---")
    if state.user_email and state.assistant_response:
        try:
            # Add RE: to the subject if it's not already there
            if not state.subject.startswith("RE:"):
                subject = "RE: " + state.subject
            else:
                subject = state.subject
            gmail_service_instance = gmail_service.authenticate_gmail()
            if gmail_service_instance:
                gmail_service.send_email(
                    gmail_service_instance,
                    state["user_email"],
                    subject,
                    state["generated_response"]
                )
                print(f"Response sent to {state['user_email']}.")
            else:
                raise Exception("Failed to authenticate with Gmail API.")
        except Exception as e:
            print(f"Error sending email: {e}")
            raise e
    else:
        print("Skipping send: No email address or no response generated.")
    return "save_state"

def save_state(state: EmailConversationState) -> str:
    """
    This function saves the conversation history to the database.
    """
    print("---NODE: Save State---")

    for message in state.new_chat_history:
        if message not in state.chat_history:
            # Save to database
            conversation_database.save_conversation(
                conversation_id=state.thread_id,
                user_email=state.user_email,
                message=message.content,
                response=state.assistant_response
            )

    return "save_state"

# Create the compiled graph instance
app = create_email_conversation_graph() 