from datetime import datetime
from typing import Any, Dict, Optional
import services.gmail_service as gmail_service
from services.delivery_manager import DeliveryManager
from email_conversation_manager.types import EmailConversationState
from email_conversation_manager import app as conversation_app
from repositories.state_repository import StateRepository
from .base_controller import BaseController

class EmailController(BaseController):
    """Controller for handling email-based interactions."""
    
    def __init__(self):
        self.gmail_service = gmail_service
        self.delivery_manager = DeliveryManager()
        self.state_repository = StateRepository()

    def process_input(self, email_data: Dict[str, Any]) -> None:
        """
        Process an incoming email. 
        This funtion checks if the email is a reply to an existing conversation or a new one.
        It will invoke the conversation manager to process the email. 
        After processing the email, it will call another function that will save the state to the database and send a response email if applicable.

        Args:
            email_data: Dictionary containing email metadata and content
        """
        msg_id = email_data['id']
        thread_id = email_data.get('threadId')
        
        # Get email details
        email_details = self._get_email_details(msg_id)
        if not email_details:
            return

        subject = email_details.get('subject', 'No subject')

        # Parse email information
        parsed_info = self._parse_email_details(email_details)
        if not parsed_info:
            return

        # Create or fetch conversation state
        state = self._prepare_conversation_state(
            thread_id=thread_id,
            sender_email=parsed_info['sender_email'],
            email_body=parsed_info['body']
        )

        # Run conversation workflow
        final_state = conversation_app.invoke(state)
        
        # Convert AddableValuesDict back to EmailConversationState if needed
        if not isinstance(final_state, EmailConversationState):
            final_state = EmailConversationState(**final_state)

        # Save state and send response
        self._handle_final_state(final_state, thread_id, msg_id, subject)

    def _get_email_details(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Get email details from Gmail API."""
        service = self.gmail_service.authenticate_gmail()
        if not service:
            return None

        email_details = self.gmail_service.get_email_details(service, msg_id, format='full')
        if not email_details or not email_details.get('payload'):
            print(f"Could not retrieve full details for email ID: {msg_id}")
            return None

        return email_details

    def _parse_email_details(self, email_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse email details into a structured format."""
        parsed_info = self.gmail_service.parse_email_details(email_details.get('payload'))
        if not parsed_info or not parsed_info.get('body'):
            return None

        return parsed_info

    def _prepare_conversation_state(
        self, 
        thread_id: Optional[str], 
        sender_email: str, 
        email_body: str
    ) -> EmailConversationState:
        """Prepare the initial state for the conversation workflow."""
        # Get existing state if available
        existing_state = None
        if thread_id:
            existing_state = self.state_repository.get_state(thread_id)
        
        # Create initial state
        initial_state = EmailConversationState(
            thread_id=thread_id,
            last_updated=datetime.now().isoformat(),
            user_input=email_body,
            user_email=sender_email,
            user_name="",
            appended_chat_history=[],
            previous_chat_history=[],
            classified_intent=None,
            available_slots=None,
            booked_slot=None,
            generated_response=None,
            error_message=None,
            booking_link=None,
            event_type_slug=None
        )
        
        # Update with existing state if available
        if existing_state:
            # Convert chat_history to previous_chat_history
            initial_state.previous_chat_history = existing_state.chat_history
            initial_state.user_email = existing_state.user_email
            initial_state.user_name = existing_state.user_name
            initial_state.last_updated = existing_state.last_updated
            # Preserve booking context
            initial_state.available_slots = existing_state.available_slots
            initial_state.booked_slot = existing_state.booked_slot
        
        return initial_state

    def _handle_final_state(
        self, 
        final_state: EmailConversationState, 
        thread_id: Optional[str], 
        msg_id: str,
        message_subject: str
    ) -> None:
        """Handle the final state after conversation processing."""
        try:
            # Ensure thread_id is set on the state
            if thread_id:
                final_state.thread_id = thread_id
                final_state.last_updated = datetime.now().isoformat()
            
            # Initialize available_slots and booked_slot if they don't exist
            if not hasattr(final_state, 'available_slots'):
                final_state.available_slots = None
            if not hasattr(final_state, 'booked_slot'):
                final_state.booked_slot = None
            
            # Save state if we have a thread_id
            if thread_id:
                self.state_repository.save_state(thread_id, final_state)
            
            # Send response email if we have a generated response
            if final_state.generated_response:
                # Add "Re: " prefix to subject if not already present
                subject = message_subject
                if not subject.lower().startswith('re:'):
                    subject = f"Re: {subject}"
                
                self.delivery_manager.send_email_response(
                    to=final_state.user_email,
                    subject=subject,
                    body=final_state.generated_response
                )
                
                # Mark original email as read
                service = self.gmail_service.authenticate_gmail()
                if service:
                    self.gmail_service.mark_email_as_read(service, msg_id)
                
        except Exception as e:
            print(f"Error handling final state: {e}")
            # Try to save error state if we have a thread_id
            if thread_id:
                try:
                    final_state.error_message = str(e)
                    self.state_repository.save_state(thread_id, final_state)
                except Exception as save_error:
                    print(f"Failed to save error state: {save_error}")

    def cleanup_old_conversations(self, days: int = 30) -> None:
        """Clean up old conversations from the database."""
        try:
            # Get list of active conversations
            active_conversations = self.state_repository.list_active_conversations(days)
            
            # Delete conversations older than the specified days
            for conversation in active_conversations:
                if conversation.thread_id:
                    self.state_repository.delete_state(conversation.thread_id)
            
            print(f"Cleaned up conversations older than {days} days")
        except Exception as e:
            print(f"Error cleaning up old conversations: {e}") 