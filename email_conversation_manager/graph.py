from langgraph.graph import StateGraph, END
import services.llm_service as llm_service

from .types import EmailConversationState, Intent
from .nodes import (
    new_interaction,
    classify_intent_node,
    gather_information_node,
    book_a_meeting_node,
    generate_response_node,
    end_interaction_node
)

def create_conversation_graph() -> StateGraph:
    """Creates and configures the conversation workflow graph."""
    workflow = StateGraph(EmailConversationState)

    # Add nodes
    workflow.add_node("new_interaction", new_interaction)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("gather_information", gather_information_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("book_a_meeting", book_a_meeting_node)
    workflow.add_node("end_interaction", end_interaction_node)

    # Set entry point
    workflow.set_entry_point("new_interaction")

    # Add edges
    workflow.add_edge("new_interaction", "classify_intent")

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

    workflow.add_edge("book_a_meeting", "generate_response")
    workflow.add_edge("gather_information", "generate_response")
    workflow.add_edge("generate_response", "end_interaction")

    workflow.add_edge("end_interaction", END)

    return workflow.compile()


def decide_next_step_after_classification(state: EmailConversationState) -> str:
    print("---DECISION: After Classification---")
    intent = state.classified_intent
    if state.error_message and intent == Intent.UNSURE:
        print("Decision: Error during classification, ending interaction.")
        return "end_interaction"

    if intent in [Intent.REQUEST_BOOKING, Intent.QUESTION_SERVICES]:
        print("Decision: Gather information for booking or service question.")
        return "gather_information"
    elif intent in [Intent.GREETING, Intent.PROVIDE_INFO, Intent.FOLLOW_UP,
                    Intent.NOT_INTERESTED_BUYING, Intent.INTERESTED_SELLING_TO_US]:
        print(f"Decision: Generate response directly for intent: {intent}")
        return "generate_response"
    elif intent == Intent.UNSURE:
        print(f"Decision: Intent is UNSURE. Generating a clarification response.")
        return "generate_response"
    elif intent == Intent.BOOK_A_MEETING:
        print(f"Decision: Book a meeting intent detected. Going to book_a_meeting.")
        return "book_a_meeting"
    else:
        print(f"Decision: Unknown or unhandled intent '{intent}', ending interaction.")
        return "end_interaction"


# Create the compiled graph instance
app = create_conversation_graph() 