from langgraph.graph import StateGraph, END
import services.llm_service as llm_service

from .state import ConversationState
from .nodes import (
    new_interaction,
    classify_intent_node,
    gather_information_node,
    book_a_meeting_node,
    generate_response_node,
    send_response_node,
    await_further_input_node,
    end_interaction_node
)

def create_conversation_graph() -> StateGraph:
    """Creates and configures the conversation workflow graph."""
    workflow = StateGraph(ConversationState)

    # Add nodes
    workflow.add_node("new_interaction", new_interaction)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("gather_information", gather_information_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("send_response", send_response_node)
    workflow.add_node("await_further_input", await_further_input_node)
    workflow.add_node("end_interaction", end_interaction_node)
    workflow.add_node("book_a_meeting", book_a_meeting_node)

    # Set entry point
    workflow.set_entry_point("new_interaction")

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

    # Add edges
    workflow.add_edge("new_interaction", "classify_intent")
    workflow.add_edge("book_a_meeting", "generate_response")
    workflow.add_edge("gather_information", "generate_response")
    workflow.add_edge("generate_response", "send_response")

    workflow.add_edge("await_further_input", "classify_intent")
    workflow.add_edge("end_interaction", END)

    return workflow.compile()


def decide_next_step_after_classification(state: ConversationState) -> str:
    print("---DECISION: After Classification---")
    intent = state.get("classified_intent")
    if state.get("error_message") and intent == llm_service.INTENT_UNSURE:
        print("Decision: Error during classification, ending interaction.")
        return "end_interaction"

    if intent in [llm_service.INTENT_REQUEST_BOOKING, llm_service.INTENT_QUESTION_SERVICES]:
        print("Decision: Gather information for booking or service question.")
        return "gather_information"
    elif intent in [llm_service.INTENT_GREETING, llm_service.INTENT_PROVIDE_INFO, llm_service.INTENT_FOLLOW_UP,
                    llm_service.INTENT_NOT_INTERESTED_BUYING, llm_service.INTENT_INTERESTED_SELLING_TO_US]:
        print(f"Decision: Generate response directly for intent: {intent}")
        return "generate_response"
    elif intent == llm_service.INTENT_UNSURE:
        print(f"Decision: Intent is UNSURE. Generating a clarification response.")
        return "generate_response"
    elif intent == llm_service.INTENT_BOOK_A_MEETING:
        print(f"Decision: Book a meeting intent detected. Going to book_a_meeting.")
        return "book_a_meeting"
    else:
        print(f"Decision: Unknown or unhandled intent '{intent}', ending interaction.")
        return "end_interaction"


def decide_after_send(state: ConversationState) -> str:
    """Decides the next step after sending a response."""
    print("---DECISION: After Sending Response---")
    intent = state.get("classified_intent")
    if state.get("error_message"):
        print("Decision: Error occurred, ending interaction.")
        return "end_interaction"
    if intent in [llm_service.INTENT_NOT_INTERESTED_BUYING, llm_service.INTENT_INTERESTED_SELLING_TO_US]:
        print(f"Decision: Definitive intent '{intent}' handled. Ending interaction.")
        return "end_interaction"
    print("Decision: Awaiting further input (next email).")
    return "await_further_input"

workflow.add_conditional_edges(
    "send_response",
    decide_after_send,
    {
        "await_further_input": "await_further_input",
        "end_interaction": "end_interaction"
    }
)


# Create the compiled graph instance
app = create_conversation_graph() 