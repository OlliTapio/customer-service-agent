from datetime import datetime
from typing import Optional, Dict, Any, List

from email_conversation_manager.types import EmailConversationDTO, EmailConversationState, ChatMessage, AvailableSlot
from repositories.database import Database


# TODO: Implement database connection and saving
class StateRepository:
    def __init__(self):
        """Initialize database connection."""
        self._db = Database()

    def get_state(self, thread_id: str) -> Optional[EmailConversationDTO]:
        """Retrieve conversation state for a given thread ID."""
        result = self._db.get_conversation(thread_id)
        if not result:
            return None
            
        conversation_data, messages = result
        
        # Convert available slots from database format to AvailableSlot objects
        available_slots = None
        if conversation_data.get('available_slots'):
            available_slots = [
                AvailableSlot(time=slot['time'], iso=slot['iso'])
                for slot in conversation_data['available_slots']
            ]
        
        # Convert booked slot from database format to AvailableSlot object
        booked_slot = None
        if conversation_data.get('booked_slot'):
            booked_slot = AvailableSlot(
                time=conversation_data['booked_slot']['time'],
                iso=conversation_data['booked_slot']['iso']
            )
        
        return EmailConversationDTO(
            thread_id=conversation_data['thread_id'],
            user_email=conversation_data['user_email'],
            user_name=conversation_data['user_name'],
            last_updated=conversation_data['last_updated'],
            available_slots=available_slots,
            booked_slot=booked_slot,
            chat_history=[ChatMessage(role=role, content=content) for role, content in messages]
        )
    
    def save_state(self, thread_id: str, state: EmailConversationState) -> None:
        """Save conversation state for a given thread ID."""
        # Prepare conversation data
        conversation_data = {
            'thread_id': state.thread_id,
            'user_email': state.user_email,
            'user_name': state.user_name,
            'last_updated': state.last_updated or datetime.now().isoformat()
        }
        
        # Add available slots if present
        if state.available_slots:
            conversation_data['available_slots'] = [
                {
                    'time': slot.time,
                    'iso': slot.iso
                }
                for slot in state.available_slots
            ]
        
        # Add booked slot if present
        if state.booked_slot:
            conversation_data['booked_slot'] = {
                'time': state.booked_slot.time,
                'iso': state.booked_slot.iso
            }
        
        # Prepare messages (only the appended chat history)
        messages = [
            (msg.role, msg.content)
            for msg in state.appended_chat_history
        ]
        
        # Save to database
        self._db.save_conversation(conversation_data, messages)

    def delete_state(self, thread_id: str) -> None:
        """Delete conversation state for a given thread ID."""
        self._db.delete_conversation(thread_id)

    def list_active_conversations(self, days: int = 30) -> List[EmailConversationDTO]:
        """List all active conversations from the last N days."""
        conversations = self._db.list_active_conversations(days)
        
        return [
            EmailConversationDTO(
                thread_id=conv_data['thread_id'],
                user_email=conv_data['user_email'],
                user_name=conv_data['user_name'],
                last_updated=conv_data['last_updated'],
                available_slots=[
                    AvailableSlot(time=slot['time'], iso=slot['iso'])
                    for slot in conv_data.get('available_slots', [])
                ] if conv_data.get('available_slots') else None,
                booked_slot=AvailableSlot(
                    time=conv_data['booked_slot']['time'],
                    iso=conv_data['booked_slot']['iso']
                ) if conv_data.get('booked_slot') else None,
                chat_history=[ChatMessage(role=role, content=content) for role, content in messages]
            )
            for conv_data, messages in conversations
        ]

# Create a singleton instance
state_repository = StateRepository() 