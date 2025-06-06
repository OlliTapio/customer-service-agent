from typing import Any, Dict
# main.py
import time
import services.gmail_service as gmail_service
import services.llm_service as llm_service
import config
from datetime import datetime
from controllers.email_controller import EmailController


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