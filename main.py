from typing import Any, Dict
# main.py
import time
from email_conversation_manager.types import EmailConversationDTO, EmailConversationState
from repositories.state_repository import StateRepository
import services.gmail_service as gmail_service
import services.llm_service as llm_service
import services.cal_service as cal_service
import config
import email_conversation_manager
from datetime import datetime
from controllers.email_controller import EmailController

def process_single_email(service: Any, email_summary: Dict[str, Any]) -> None:
    """Processes a single email: gets details, generates reply, sends reply, marks as read."""
    msg_id = email_summary['id']
    thread_id = email_summary.get('threadId')  # Get Gmail's thread ID
    print(f"\nProcessing email ID: {msg_id} (Thread ID: {thread_id})...")

    email_details = gmail_service.get_email_details(service, msg_id, format='full')
    if not email_details or not email_details.get('payload'):
        print(f"Could not retrieve full details for email ID: {msg_id}")
        return

    parsed_info = gmail_service.parse_email_details(email_details.get('payload'))
    if not parsed_info or not parsed_info.get('body'):
        print(f"Could not parse body or essential details for email ID: {msg_id}")
        return

    sender_email = parsed_info['sender']
    original_subject = parsed_info['subject']
    email_body = parsed_info['body']

    print(f"  From: {sender_email}")
    print(f"  Subject: {original_subject}")
    # Prepare body snippet outside f-string to avoid backslash issue
    body_snippet = email_body[:100].replace('\n', ' ')
    print(f"  Body Snippet: {body_snippet}...")

    if not email_body.strip(): # Don't process empty emails
        print("  Email body is empty. Skipping processing and marking as read.")
        gmail_service.mark_email_as_read(service, msg_id)
        return
    
    # Try to load existing state from database
    existing_state: EmailConversationDTO | None = None
    if thread_id:
        existing_state = StateRepository.get_state(thread_id)
    
    # Prepare initial state for LangGraph
    initial_state = EmailConversationState(
        thread_id=thread_id,  # Use Gmail's thread ID
        last_updated=datetime.now().isoformat(),
        user_input=email_body,
        user_email=sender_email,
        user_name=None,  # Optionally parse from email or headers
        appended_chat_history=[],
        previous_chat_history=[],
        classified_intent=None,
        available_slots=None,
        generated_response=None,
        error_message=None,
        booking_link=None,
        event_type_slug=None
    )

    # If we have existing state, update the initial state with it
    if existing_state:
        initial_state.previous_chat_history = existing_state.chat_history
        initial_state.user_email = existing_state.user_email
        initial_state.user_name = existing_state.user_name
        initial_state.last_updated = existing_state.last_updated

    # Save the initial state to database
    if thread_id:
        StateRepository.save_state(thread_id, initial_state)

    # Run through the LangGraph workflow
    print("  Running LangGraph conversation manager...")
    final_state = email_conversation_manager.app.invoke(initial_state)

    # Save the final state to database
    if thread_id:
        final_state.last_updated = datetime.now().isoformat()
        StateRepository.save_state(thread_id, final_state)
        print(f"Saved final state to database for thread {thread_id}")

    # Optionally print the final state for debugging
    print(f"  Final classified intent: {final_state.get('classified_intent')}")
    print(f"  Final generated response: {final_state.get('generated_response')}")
    if final_state.get('error_message'):
        print(f"  Error: {final_state.get('error_message')}")

    # Mark original email as read
    gmail_service.mark_email_as_read(service, msg_id)
    print(f"Email ID: {msg_id} processed and marked as read.")

def main() -> None:
    """Main function to start the AI Email Assistant."""
    print("Starting AI Email Assistant...")

    if not llm_service.llm_model:
        print("LLM Model not initialized. Please check Gemini API Key and llm_service.py. Exiting.")
        return
        
    print("Authenticating with Gmail...")
    gmail_api_service = gmail_service.authenticate_gmail()
    if not gmail_api_service:
        print("Gmail authentication failed. Please check credentials and OAuth consent. Exiting.")
        return
    print("Successfully authenticated with Gmail.")

    email_controller = EmailController()

    print(f"Checking for unread emails to {config.ASSISTANT_EMAIL}...")
    unread_emails = gmail_service.get_unread_emails(gmail_api_service)

    if not unread_emails:
        print("No unread emails found.")
    else:
        print(f"Found {len(unread_emails)} unread email(s).")
        for email_summary in unread_emails:
            try:
                email_controller.process_input(email_summary)
                time.sleep(2)  # Small delay between processing emails
            except Exception as e:
                print(f"An unexpected error occurred processing email ID {email_summary.get('id', 'N/A')}: {e}")

    print("\nAI Email Assistant run complete.")

if __name__ == '__main__':
    main()