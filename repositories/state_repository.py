from datetime import datetime
from typing import Optional, Dict, Any, List
import sqlite3

from email_conversation_manager.types import EmailConversationDTO, EmailConversationState, ChatMessage, AvailableSlot
from repositories.database import Database


class StateRepository:
    def __init__(self):
        """Initialize database connection."""
        self._db = Database()

    def get_state(self, thread_id: str) -> Optional[EmailConversationDTO]:
        """Retrieve conversation state for a given thread ID."""
        try:
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
        except sqlite3.Error as e:
            print(f"Database error while getting state: {e}")
            return None
    
    def save_state(self, thread_id: str, state: EmailConversationState) -> None:
        """Save conversation state for a given thread ID."""
        try:
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
            
            # Add booking link and event type if present
            if state.booking_link:
                conversation_data['booking_link'] = state.booking_link
            if state.event_type_slug:
                conversation_data['event_type_slug'] = state.event_type_slug
            
            # Prepare messages (combine previous and appended chat history)
            messages = [
                (msg.role, msg.content)
                for msg in state.previous_chat_history + state.appended_chat_history
            ]
            
            # Save to database
            self._db.save_conversation(conversation_data, messages)
        except sqlite3.Error as e:
            print(f"Database error while saving state: {e}")
            raise

    def delete_state(self, thread_id: str) -> None:
        """Delete conversation state for a given thread ID."""
        try:
            self._db.delete_conversation(thread_id)
        except sqlite3.Error as e:
            print(f"Database error while deleting state: {e}")
            raise

    def list_active_conversations(self, days: int = 30) -> List[EmailConversationDTO]:
        """List all active conversations from the last N days."""
        try:
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
        except sqlite3.Error as e:
            print(f"Database error while listing active conversations: {e}")
            return []

    def cleanup_old_states(self, days: int = 30) -> None:
        """Clean up old conversation states."""
        try:
            self._db.cleanup_old_states(days)
        except sqlite3.Error as e:
            print(f"Database error while cleaning up old states: {e}")
            raise

# Create a singleton instance
state_repository = StateRepository() 