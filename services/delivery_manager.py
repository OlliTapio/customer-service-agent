from typing import Optional, Dict, Any
import services.gmail_service as gmail_service
from email_conversation_manager.types import EmailConversationState
import config

class DeliveryManager:
    def __init__(self):
        self.gmail_service = gmail_service

    def send_email_response(self, to: str, subject: str, body: str) -> Optional[Dict[str, Any]]:
        """
        Sends an email response using the Gmail service.
        Returns the message details if successful, None if failed.
        """
        if not to or not body:
            print("Skipping send: No email address or no response generated.")
            return None

        if config.SKIP_SENDING_EMAILS:
            print(f"[SKIP_SENDING_EMAILS] Would have sent email to {to} with subject: {subject}")
            print(f"[SKIP_SENDING_EMAILS] Email body: {body}")
            return {"id": "skipped", "to": to, "subject": subject}

        try:
            gmail_service_instance = self.gmail_service.authenticate_gmail()
            
            if not gmail_service_instance:
                print("Failed to authenticate with Gmail API.")
                return None

            message = self.gmail_service.send_email(
                gmail_service_instance,
                to,
                subject,
                body
            )
            
            print(f"Response sent to {to}.")
            return message

        except Exception as e:
            print(f"Error sending email: {e}")
            return None

    def send_voice_response(self, state: EmailConversationState) -> bool:
        """
        Sends a voice response (to be implemented).
        Returns True if successful, False if failed.
        """
        # TODO: Implement voice response delivery
        return False 