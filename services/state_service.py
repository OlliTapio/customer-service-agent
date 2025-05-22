from datetime import datetime
from typing import Optional, Dict, Any

class StateService:
    def __init__(self):
        """Initialize in-memory state storage."""
        self._states = {}

    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversation state for a given thread ID."""
        return self._states.get(thread_id)

    def save_state(self, thread_id: str, state: Dict[str, Any]) -> None:
        """Save conversation state for a given thread ID."""
        state_to_save = state.copy()
        if 'last_updated' in state_to_save:
            state_to_save['last_updated'] = datetime.now().isoformat()
        
        self._states[thread_id] = state_to_save

    def delete_state(self, thread_id: str) -> None:
        """Delete conversation state for a given thread ID."""
        if thread_id in self._states:
            del self._states[thread_id]

    def list_active_conversations(self, days: int = 30) -> list:
        """List all active conversations from the last N days."""
        cutoff_date = datetime.now() - datetime.timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat()
        
        return [
            state for state in self._states.values()
            if state.get('last_updated', '') >= cutoff_iso
        ]

# Create a singleton instance
state_service = StateService() 