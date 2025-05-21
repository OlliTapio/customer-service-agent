from google.cloud import firestore
from datetime import datetime
from typing import Optional, Dict, Any
import config

class StateService:
    def __init__(self):
        """Initialize Firestore client."""
        self.db = firestore.Client()
        self.collection = self.db.collection('conversation_states')

    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversation state for a given thread ID."""
        doc_ref = self.collection.document(thread_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    def save_state(self, thread_id: str, state: Dict[str, Any]) -> None:
        """Save conversation state for a given thread ID."""
        # Convert datetime objects to ISO format strings
        state_to_save = state.copy()
        if 'last_updated' in state_to_save:
            state_to_save['last_updated'] = datetime.now().isoformat()
        
        # Save to Firestore
        doc_ref = self.collection.document(thread_id)
        doc_ref.set(state_to_save)

    def delete_state(self, thread_id: str) -> None:
        """Delete conversation state for a given thread ID."""
        doc_ref = self.collection.document(thread_id)
        doc_ref.delete()

    def list_active_conversations(self, days: int = 30) -> list:
        """List all active conversations from the last N days."""
        cutoff_date = datetime.now() - datetime.timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat()
        
        query = self.collection.where('last_updated', '>=', cutoff_iso)
        return [doc.to_dict() for doc in query.stream()]

# Create a singleton instance
state_service = StateService() 