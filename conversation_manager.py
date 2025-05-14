from typing import TypedDict, List, Optional, Any
from langgraph.graph import StateGraph, END

# Import services and config
import llm_service  # Assuming llm_service.py is in the same directory or accessible via PYTHONPATH
import cal_service  # Assuming cal_service.py is in the same directory
import config       # For CAL_COM_USERNAME, CAL_COM_EVENT_TYPE_SLUG etc.

# 1. Define the state schema (ensure it aligns with what services need and produce)
class ConversationState(TypedDict):
    user_input: Optional[str]
    user_email: Optional[str]
    user_name: Optional[str]
    interaction_history: List[str]
    classified_intent: Optional[str]
    available_slots: Optional[List[dict]]
    generated_response: Optional[str]
    error_message: Optional[str]
    # Add fields that might be needed by services or for graph logic
    booking_link: Optional[str]      # Can be pre-set or generated
    event_type_slug: Optional[str]   # To help generate booking_link or fetch slots


# 2. Define the nodes
def new_interaction(state: ConversationState) -> ConversationState:
    print("---NODE: New Interaction---")
    if not state.get("interaction_history"):
        state["interaction_history"] = []
    
    # Initialize event_type_slug from config if not already set (e.g. by a calling function)
    if not state.get("event_type_slug") and hasattr(config, 'CAL_COM_EVENT_TYPE_SLUG'):
        state["event_type_slug"] = config.CAL_COM_EVENT_TYPE_SLUG
        print(f"Initialized event_type_slug from config: {state['event_type_slug']}")

    # Initialize booking_link from config if not already set
    if not state.get("booking_link") and hasattr(config, 'CAL_COM_USERNAME') and state.get("event_type_slug"):
        state["booking_link"] = f"https://cal.com/{config.CAL_COM_USERNAME}/{state['event_type_slug']}"
        print(f"Initialized booking_link: {state['booking_link']}")

    if state.get("user_input"): # Add current user input to history
        state["interaction_history"].append(f"User: {state['user_input']}")
    print(f"User input: {state.get('user_input')}")
    # Reset fields that should be determined in this run
    state["classified_intent"] = None
    state["available_slots"] = None
    state["generated_response"] = None
    state["error_message"] = None
    return state

def classify_intent_node(state: ConversationState) -> ConversationState: # Renamed to avoid conflict
    print("---NODE: Classify Intent---")
    if not state.get("user_input"):
        state["error_message"] = "No user input to classify."
        state["classified_intent"] = llm_service.INTENT_UNSURE
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
        return state

    try:
        intent = llm_service.classify_user_intent(
            user_input=state["user_input"],
            conversation_history=state.get("interaction_history", [])
        )
        state["classified_intent"] = intent
        state["interaction_history"].append(f"System: Classified intent as {intent}")
        print(f"Classified intent: {intent}")
    except Exception as e:
        print(f"Error during intent classification: {e}")
        state["error_message"] = f"Failed to classify intent: {e}"
        state["classified_intent"] = llm_service.INTENT_UNSURE
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
    return state

def gather_information_node(state: ConversationState) -> ConversationState: # Renamed
    print("---NODE: Gather Information---")
    intent = state.get("classified_intent")
    
    if intent == llm_service.INTENT_REQUEST_BOOKING:
        print("Attempting to fetch calendar availability...")
        try:
            event_slug_to_use = state.get("event_type_slug")
            if not event_slug_to_use and hasattr(config, 'CAL_COM_EVENT_TYPE_SLUG'):
                event_slug_to_use = config.CAL_COM_EVENT_TYPE_SLUG
            
            if not event_slug_to_use:
                state["error_message"] = "Event type slug not configured or found in state."
                print(state["error_message"])
                state["interaction_history"].append(f"System: Error - {state['error_message']}")
                # No slots, response generation will handle this
                state["available_slots"] = [] 
                return state

            # Fetch event type details first to get numeric ID for V1 availability
            event_details_v2 = cal_service.get_event_type_details_v2(
                user_cal_username=config.CAL_COM_USERNAME, 
                event_type_slug=event_slug_to_use
            )
            if event_details_v2 and event_details_v2.get("id"):
                event_type_id_v1 = event_details_v2["id"]
                print(f"Fetched V2 event details, found V1 compatible ID: {event_type_id_v1} for slug {event_slug_to_use}")
                
                # Now fetch slots using the V1 endpoint and the numeric ID
                raw_slots = cal_service.get_available_slots_v1(
                    api_key=config.CAL_COM_API_KEY, # Assuming cal_service handles this or it's passed
                    event_type_id=str(event_type_id_v1), # V1 uses string ID
                    days_in_future=14 # Or make this configurable
                )
                # The v1 function returns a list of slot start times directly (strings)
                # We need to structure them as list of dicts for generate_contextual_response
                formatted_slots = [{"time": slot_time} for slot_time in raw_slots] if raw_slots else []

                state["available_slots"] = formatted_slots
                state["interaction_history"].append(f"System: Fetched {len(formatted_slots)} available slots.")
                print(f"Fetched {len(formatted_slots)} available slots: {formatted_slots[:3]}...") # Log first few
            else:
                error_msg = f"Could not fetch V2 event details or ID for slug {event_slug_to_use} to get V1 slots."
                print(error_msg)
                state["error_message"] = error_msg
                state["interaction_history"].append(f"System: Error - {error_msg}")
                state["available_slots"] = []

        except Exception as e:
            error_msg = f"Error fetching calendar availability: {e}"
            print(error_msg)
            state["error_message"] = error_msg
            state["interaction_history"].append(f"System: Error - {error_msg}")
            state["available_slots"] = [] # Ensure it's an empty list on error
            
    # Add other info gathering logic here if needed for other intents
    return state

def generate_response_node(state: ConversationState) -> ConversationState: # Renamed
    print("---NODE: Generate Response---")
    if not state.get("classified_intent"):
        state["generated_response"] = "I'm sorry, I wasn't able to understand your request. Could you please rephrase?"
        state["error_message"] = "Cannot generate response: Intent not classified."
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
        return state

    try:
        response_text = llm_service.generate_contextual_response(
            intent=state["classified_intent"],
            user_input=state.get("user_input", ""),
            conversation_history=state.get("interaction_history", []),
            user_name=state.get("user_name"),
            available_slots=state.get("available_slots"),
            booking_link=state.get("booking_link"), # Ensure this is populated
            event_type_slug=state.get("event_type_slug"), # Ensure this is populated
            website_info="OTL.fi specializes in innovative tech solutions. For detailed discussions, a call is recommended." # Or from config/state
        )
        state["generated_response"] = response_text
        state["interaction_history"].append(f"System: Generated response: {response_text}")
        print(f"Generated response: {response_text}")
    except Exception as e:
        print(f"Error during response generation: {e}")
        state["error_message"] = f"Failed to generate response: {e}"
        state["generated_response"] = "I apologize, I encountered an error while trying to generate a response. Please try again."
        state["interaction_history"].append(f"System: Error - {state['error_message']}")
    return state

def send_response_node(state: ConversationState) -> ConversationState: # Renamed
    print("---NODE: Send Response---")
    # Placeholder for sending the response (e.g., via Gmail API or TTS for a call)
    # Uses state["generated_response"] and state["user_email"]
    print(f"Simulating sending to {state.get('user_email')}: {state.get('generated_response')}")
    # Example:
    # if state.get("user_email") and state.get("generated_response"):
    #     try:
    #         import gmail_service # Assuming you have this service
    #         gmail_service.send_email(
    #             to=state["user_email"],
    #             subject="Re: Your Inquiry", # Or a more dynamic subject
    #             body=state["generated_response"]
    #         )
    #         state["interaction_history"].append(f"System: Sent response to {state['user_email']}.")
    #         print(f"Response sent to {state['user_email']}.")
    #     except Exception as e:
    #         print(f"Error sending email: {e}")
    #         state["error_message"] = f"Failed to send email: {e}"
    #         state["interaction_history"].append(f"System: Error - {state['error_message']}")
    # else:
    #     print("Skipping send: No email address or no response generated.")
    #     state["interaction_history"].append("System: Skipped sending response (no email/response).")
    
    # For now, just log it
    state["interaction_history"].append(f"System: Response intended to be sent: {state.get('generated_response')}")
    # Clear the generated response after "sending" to avoid resending if the graph loops in a way that doesn't repopulate
    # state["generated_response"] = None # Or LangGraph manages state copies per invocation. Typically, it's better to be explicit.
    return state

def await_further_input_node(state: ConversationState) -> ConversationState: # Renamed
    print("---NODE: Await Further Input---")
    state["interaction_history"].append("System: Awaiting further input from user.")
    print("Waiting for next user input...")
    # In a real scenario, the application would pause here or this state would signify the end of
    # the current processing cycle, waiting for an external trigger (new email, new voice input).
    return state

def end_interaction_node(state: ConversationState) -> ConversationState: # Renamed
    print("---NODE: End Interaction---")
    state["interaction_history"].append("System: Interaction ended.")
    print("Interaction ended.")
    # Final clean-up or logging can happen here.
    return state


# 3. Define the graph
workflow = StateGraph(ConversationState)

# Add nodes with new names
workflow.add_node("new_interaction", new_interaction)
workflow.add_node("classify_intent", classify_intent_node) # Use new name
workflow.add_node("gather_information", gather_information_node) # Use new name
workflow.add_node("generate_response", generate_response_node) # Use new name
workflow.add_node("send_response", send_response_node) # Use new name
workflow.add_node("await_further_input", await_further_input_node) # Use new name
workflow.add_node("end_interaction", end_interaction_node) # Use new name


# 4. Define the edges

workflow.set_entry_point("new_interaction")
workflow.add_edge("new_interaction", "classify_intent")

def decide_next_step_after_classification(state: ConversationState) -> str:
    print("---DECISION: After Classification---")
    intent = state.get("classified_intent")
    if state.get("error_message") and intent == llm_service.INTENT_UNSURE: # Error in classification
        print("Decision: Error during classification, ending interaction.")
        return "end_interaction"

    if intent == llm_service.INTENT_REQUEST_BOOKING:
        print("Decision: Gather information for booking.")
        return "gather_information"
    elif intent in [llm_service.INTENT_GREETING, llm_service.INTENT_GENERAL_QUERY, 
                    llm_service.INTENT_QUESTION_SERVICES, llm_service.INTENT_PROVIDE_INFO,
                    llm_service.INTENT_FOLLOW_UP, llm_service.INTENT_NOT_INTERESTED_BUYING,
                    llm_service.INTENT_INTERESTED_SELLING_TO_US]:
        print(f"Decision: Generate response directly for intent: {intent}")
        return "generate_response"
    elif intent == llm_service.INTENT_UNSURE:
         print(f"Decision: Intent is UNSURE. Generating a clarification response.")
         return "generate_response" # Let generate_response handle UNSURE by asking for clarification
    else: 
        print(f"Decision: Unknown or unhandled intent '{intent}', ending interaction.")
        return "end_interaction"

workflow.add_conditional_edges(
    "classify_intent",
    decide_next_step_after_classification,
    {
        "gather_information": "gather_information",
        "generate_response": "generate_response",
        "end_interaction": "end_interaction",
    }
)

# Edge from gather_information (which might have errors) to generate_response
workflow.add_edge("gather_information", "generate_response")
workflow.add_edge("generate_response", "send_response")

def decide_after_send(state: ConversationState) -> str:
    print("---DECISION: After Sending Response---")
    intent = state.get("classified_intent")
    # If the interaction was definitive (e.g., not interested, selling to us, or a simple query handled)
    # or if an error occurred that prevents continuation, we might end.
    if state.get("error_message") and "Failed to send email" in state["error_message"]: # Critical send error
        return "end_interaction"
    if intent in [llm_service.INTENT_NOT_INTERESTED_BUYING, llm_service.INTENT_INTERESTED_SELLING_TO_US]:
        print(f"Decision: Definitive intent {intent} handled. Ending interaction.")
        return "end_interaction"
    # For most other cases in an email bot, we await the next user email, effectively ending this run.
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

workflow.add_edge("await_further_input", END) # End of this processing cycle
workflow.add_edge("end_interaction", END)     # Explicit end state


# 5. Compile the graph
app = workflow.compile()

# 6. Example Usage (basic test)
if __name__ == "__main__":
    print("--- Running Conversation Manager Tests ---")

    # Common details from config needed for tests
    test_event_slug = getattr(config, 'CAL_COM_EVENT_TYPE_SLUG', '30min')
    test_booking_link = f"https://cal.com/{getattr(config, 'CAL_COM_USERNAME', 'testuser')}/{test_event_slug}"


    test_cases = [
        {
            "name": "Booking Request",
            "initial_state": ConversationState(
                user_input="Hi, I'd like to book a meeting.",
                user_email="booker@example.com", user_name="Booker Bob",
                interaction_history=[], event_type_slug=test_event_slug, booking_link=test_booking_link
            )
        },
        {
            "name": "Greeting",
            "initial_state": ConversationState(
                user_input="Hello there!",
                user_email="greeter@example.com", user_name="Friendly Fred",
                interaction_history=[], event_type_slug=test_event_slug, booking_link=test_booking_link
            )
        },
        {
            "name": "General Query",
            "initial_state": ConversationState(
                user_input="What services do you offer for cloud migration?",
                user_email="query@example.com", user_name="Curious Carla",
                interaction_history=[], event_type_slug=test_event_slug, booking_link=test_booking_link
            )
        },
        {
            "name": "Selling to Us",
            "initial_state": ConversationState(
                user_input="I have an amazing new AI tool I want to sell to OTL.fi!",
                user_email="seller@example.com", user_name="Salesy Sam",
                interaction_history=[], event_type_slug=test_event_slug, booking_link=test_booking_link
            )
        },
        {
            "name": "Not Interested",
            "initial_state": ConversationState(
                user_input="Thanks for the info, but I'm not interested right now.",
                user_email="no@example.com", user_name="Declining Dan",
                interaction_history=[], event_type_slug=test_event_slug, booking_link=test_booking_link
            )
        },
        {
            "name": "Unclear Input",
            "initial_state": ConversationState(
                user_input="Grmphflx zzz.", # Intentionally unclear
                user_email="unclear@example.com", user_name="Mumbling Mike",
                interaction_history=[], event_type_slug=test_event_slug, booking_link=test_booking_link
            )
        }
    ]

    for test_case in test_cases:
        print(f"\\n--- Running Test: {test_case['name']} ---")
        print(f"Initial User Input: {test_case['initial_state']['user_input']}")
        
        # For streaming output:
        # for event in app.stream(test_case["initial_state"]):
        #     for key, value in event.items():
        #         print(f"Node '{key}' output relevant keys:")
        #         if "interaction_history" in value:
        #             print(f"  Last history entry: {value['interaction_history'][-1] if value['interaction_history'] else 'N/A'}")
        #         if "classified_intent" in value and value["classified_intent"] is not None:
        #             print(f"  Intent: {value['classified_intent']}")
        #         if "generated_response" in value and value["generated_response"] is not None:
        #             print(f"  Response: {value['generated_response'][:100]}...") # Print snippet
        #         if "error_message" in value and value["error_message"] is not None:
        #             print(f"  Error: {value['error_message']}")
        #     print("\\n---\\n")
        
        final_state = app.invoke(test_case["initial_state"])
        print(f"\\n--- Test '{test_case['name']}' Final State Snippet ---")
        print(f"Last User Input: {final_state.get('user_input')}")
        print(f"Classified Intent: {final_state.get('classified_intent')}")
        print(f"Generated Response: {final_state.get('generated_response')}")
        if final_state.get('error_message'):
            print(f"Error Message: {final_state.get('error_message')}")
        print(f"Interaction History Snippet (last 3):")
        for entry in final_state.get("interaction_history", [])[-3:]:
            print(f"  {entry}")
        print("\\n" + "="*40 + "\\n")

    # Visualization code moved out as per user request
    # try:
    #     print("\\n--- Generating Graph PNG (requires Mermaid/Playwright) ---")
    #     img_bytes = app.get_graph().draw_mermaid_png()
    #     with open("graph.png", "wb") as f:
    #         f.write(img_bytes)
    #     print("Graph PNG saved to graph.png")
    # except Exception as e:
    #     print(f"\\nCould not generate or save graph PNG: {e}")
    #     print("Ensure dependencies like playwright are installed ('pip install langgraph[draw]', then 'playwright install').")

