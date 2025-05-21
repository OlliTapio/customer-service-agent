from langgraph.graph import StateGraph, END
import services.llm_service as llm_service

from .state import EmailConversationState

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


# Create the compiled graph instance
app = create_email_conversation_graph() 