import unittest
from datetime import datetime, timedelta
import os

from email_conversation_manager.types import EmailConversationState, ChatMessage, Intent
from repositories.state_repository import state_repository

class TestStateService(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Use a test database file
        self.test_db_path = "test_conversations.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        # Create a test state
        self.test_state = EmailConversationState(
            thread_id="test_thread_123",
            user_email="test@example.com",
            user_name="Test User",
            previous_chat_history=[
                ChatMessage(role="user", content="Hello"),
                ChatMessage(role="assistant", content="Hi there!")
            ],
            appended_chat_history=[
                ChatMessage(role="user", content="How are you?"),
                ChatMessage(role="assistant", content="I'm doing well, thanks!")
            ]
        )

    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_save_and_get_state(self):
        """Test saving and retrieving a conversation state."""
        # Save the state
        state_repository.save_state(self.test_state.thread_id, self.test_state)
        
        # Retrieve the state
        retrieved_state = state_repository.get_state(self.test_state.thread_id)
        
        # Verify the retrieved state
        self.assertIsNotNone(retrieved_state)
        self.assertEqual(retrieved_state.thread_id, self.test_state.thread_id)
        self.assertEqual(retrieved_state.user_email, self.test_state.user_email)
        self.assertEqual(retrieved_state.user_name, self.test_state.user_name)
        
        # Verify chat history
        expected_history = self.test_state.previous_chat_history + self.test_state.appended_chat_history
        self.assertEqual(len(retrieved_state.chat_history), len(expected_history))
        for i, msg in enumerate(expected_history):
            self.assertEqual(retrieved_state.chat_history[i].role, msg.role)
            self.assertEqual(retrieved_state.chat_history[i].content, msg.content)

    def test_delete_state(self):
        """Test deleting a conversation state."""
        # Save the state
        state_repository.save_state(self.test_state.thread_id, self.test_state)
        
        # Verify it exists
        self.assertIsNotNone(state_repository.get_state(self.test_state.thread_id))
        
        # Delete the state
        state_repository.delete_state(self.test_state.thread_id)
        
        # Verify it's gone
        self.assertIsNone(state_repository.get_state(self.test_state.thread_id))

    def test_list_active_conversations(self):
        """Test listing active conversations."""
        # Save multiple states
        for i in range(3):
            state = EmailConversationState(
                thread_id=f"test_thread_{i}",
                user_email=f"user{i}@example.com",
                user_name=f"User {i}",
                previous_chat_history=[ChatMessage(role="user", content=f"Test message {i}")],
                appended_chat_history=[]
            )
            state_repository.save_state(state.thread_id, state)
        
        # List active conversations
        active_conversations = state_repository.list_active_conversations(days=1)
        
        # Verify we got all conversations
        self.assertEqual(len(active_conversations), 3)
        
        # Verify each conversation
        for i, conv in enumerate(active_conversations):
            self.assertEqual(conv.thread_id, f"test_thread_{i}")
            self.assertEqual(conv.user_email, f"user{i}@example.com")
            self.assertEqual(conv.user_name, f"User {i}")

    def test_conversation_persistence(self):
        """Test that conversation history is properly persisted across state updates."""
        # Initial state with some history
        state_repository.save_state(self.test_state.thread_id, self.test_state)
        
        # Create a new state with additional messages
        new_messages = [
            ChatMessage(role="user", content="Can we schedule a meeting?"),
            ChatMessage(role="assistant", content="Of course! When would you like to meet?")
        ]
        
        updated_state = EmailConversationState(
            thread_id=self.test_state.thread_id,
            user_email=self.test_state.user_email,
            user_name=self.test_state.user_name,
            previous_chat_history=self.test_state.previous_chat_history + self.test_state.appended_chat_history,
            appended_chat_history=new_messages
        )
        
        # Save updated state
        state_repository.save_state(updated_state.thread_id, updated_state)
        
        # Retrieve final state
        final_state = state_repository.get_state(self.test_state.thread_id)
        
        # Verify all messages are present in correct order
        expected_history = (
            self.test_state.previous_chat_history +
            self.test_state.appended_chat_history +
            new_messages
        )
        
        self.assertEqual(len(final_state.chat_history), len(expected_history))
        for i, msg in enumerate(expected_history):
            self.assertEqual(final_state.chat_history[i].role, msg.role)
            self.assertEqual(final_state.chat_history[i].content, msg.content)

    def test_state_cleanup(self):
        """Test cleanup of old conversation states."""
        # Create multiple states with different timestamps
        states = []
        for i in range(5):
            state = EmailConversationState(
                thread_id=f"test_thread_{i}",
                user_email=f"user{i}@example.com",
                user_name=f"User {i}",
                previous_chat_history=[],
                appended_chat_history=[],
                last_updated=(datetime.now() - timedelta(days=i)).isoformat()
            )
            states.append(state)
            state_repository.save_state(state.thread_id, state)
        
        # Clean up states older than 3 days
        state_repository.cleanup_old_states(days=3)
        
        # Verify only recent states remain
        active_conversations = state_repository.list_active_conversations(days=3)
        self.assertEqual(len(active_conversations), 3)
        
        # Verify the correct states were kept
        active_thread_ids = {conv.thread_id for conv in active_conversations}
        expected_thread_ids = {f"test_thread_{i}" for i in range(3)}
        self.assertEqual(active_thread_ids, expected_thread_ids)

if __name__ == '__main__':
    unittest.main() 