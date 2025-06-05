from typing import Optional, Dict, Any
import services.gmail_service as gmail_service
from email_conversation_manager.types import EmailConversationState

class DeliveryManager:
    def __init__(self):
        self.gmail_service = gmail_service

    def send_email_response(self, state: EmailConversationState, subject: str) -> Optional[Dict[str, Any]]:
        """
        Sends an email response using the Gmail service.
        Returns the message details if successful, None if failed.
        """
        if not state.user_email or not state.generated_response:
            print("Skipping send: No email address or no response generated.")
            return None

        try:
            gmail_service_instance = self.gmail_service.authenticate_gmail()
            
            if not gmail_service_instance:
                print("Failed to authenticate with Gmail API.")
                return None

            message = self.gmail_service.send_email(
                gmail_service_instance,
                state.user_email,
                subject,
                state.generated_response
            )
            
            print(f"Response sent to {state.user_email}.")
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