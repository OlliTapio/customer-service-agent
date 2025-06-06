import unittest
from datetime import datetime, timedelta
import json

from email_conversation_manager.types import EmailConversationState, ChatMessage, Intent, AvailableSlot
from repositories.state_repository import state_repository
from repositories.database import Database

class TestStateService(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Use in-memory database for testing
        self.db = Database(":memory:")
        # Override the state_repository's database instance
        state_repository._db = self.db
        
        # Create a test state with all possible fields
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
            ],
            available_slots=[
                AvailableSlot(time="10:00", iso="2024-03-20T10:00:00Z"),
                AvailableSlot(time="11:00", iso="2024-03-20T11:00:00Z")
            ],
            booked_slot=AvailableSlot(time="10:00", iso="2024-03-20T10:00:00Z"),
            booking_link="https://calendly.com/test/meeting",
            event_type_slug="30min-meeting"
        )

    def tearDown(self):
        """Clean up after tests."""
        # No need to clean up file since we're using in-memory database
        pass

    def test_save_and_get_state(self):
        """Test saving and retrieving a conversation state with all fields."""
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
        
        # Verify available slots
        self.assertEqual(len(retrieved_state.available_slots), len(self.test_state.available_slots))
        for i, slot in enumerate(self.test_state.available_slots):
            self.assertEqual(retrieved_state.available_slots[i].time, slot.time)
            self.assertEqual(retrieved_state.available_slots[i].iso, slot.iso)
        
        # Verify booked slot
        self.assertIsNotNone(retrieved_state.booked_slot)
        self.assertEqual(retrieved_state.booked_slot.time, self.test_state.booked_slot.time)
        self.assertEqual(retrieved_state.booked_slot.iso, self.test_state.booked_slot.iso)
        

    def test_delete_state(self):
        """Test deleting a conversation state and verify cascade deletion."""
        # Save the state
        state_repository.save_state(self.test_state.thread_id, self.test_state)
        
        # Verify it exists
        self.assertIsNotNone(state_repository.get_state(self.test_state.thread_id))
        
        # Delete the state
        state_repository.delete_state(self.test_state.thread_id)
        
        # Verify it's gone
        self.assertIsNone(state_repository.get_state(self.test_state.thread_id))
        
        # Verify chat history is also deleted (cascade)
        cursor = self.db._get_connection().cursor()
        cursor.execute("SELECT COUNT(*) FROM chat_history WHERE thread_id = ?", (self.test_state.thread_id,))
        count = cursor.fetchone()[0]
        self.assertEqual(count, 0)

    def test_list_active_conversations(self):
        """Test listing active conversations with all fields."""
        # Save multiple states with different timestamps
        states = []
        for i in range(3):
            state = EmailConversationState(
                thread_id=f"test_thread_{i}",
                user_email=f"user{i}@example.com",
                user_name=f"User {i}",
                previous_chat_history=[ChatMessage(role="user", content=f"Test message {i}")],
                appended_chat_history=[],
                last_updated=(datetime.now() - timedelta(days=i)).isoformat(),
                booking_link=f"https://calendly.com/test/meeting{i}",
                event_type_slug=f"30min-meeting-{i}"
            )
            states.append(state)
            state_repository.save_state(state.thread_id, state)
        
        # List active conversations
        active_conversations = state_repository.list_active_conversations(days=1)
        
        # Verify we got only recent conversations
        self.assertEqual(len(active_conversations), 1)
        
        # Verify the conversation details
        conv = active_conversations[0]
        self.assertEqual(conv.thread_id, "test_thread_0")
        self.assertEqual(conv.user_email, "user0@example.com")
        self.assertEqual(conv.user_name, "User 0")

    def test_conversation_persistence(self):
        """Test that conversation history is properly persisted with timestamps."""
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
        
        # Verify chat history in database
        cursor = self.db._get_connection().cursor()
        cursor.execute("""
            SELECT role, content, timestamp
            FROM chat_history
            WHERE thread_id = ?
            ORDER BY id ASC
        """, (self.test_state.thread_id,))
        chat_rows = cursor.fetchall()
        
        # Verify all messages are present
        expected_history = (
            self.test_state.previous_chat_history +
            self.test_state.appended_chat_history +
            new_messages
        )
        self.assertEqual(len(chat_rows), len(expected_history))
        
        # Verify message order and content
        for i, (role, content, timestamp) in enumerate(chat_rows):
            self.assertEqual(role, expected_history[i].role)
            self.assertEqual(content, expected_history[i].content)
            # Verify timestamp is present and valid
            self.assertIsNotNone(timestamp)
            datetime.fromisoformat(timestamp)  # Should not raise exception

    def test_state_cleanup(self):
        """Test cleanup of old conversation states with proper database verification."""
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
        
        # Verify database state directly
        cursor = self.db._get_connection().cursor()
        
        # Check conversations table
        cursor.execute("SELECT COUNT(*) FROM conversations")
        conv_count = cursor.fetchone()[0]
        self.assertEqual(conv_count, 3)
        
        # Check chat_history table
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        chat_count = cursor.fetchone()[0]
        self.assertEqual(chat_count, 0)  # Since all test states had empty chat history
        
        # Verify specific conversations are gone
        cursor.execute("SELECT thread_id FROM conversations ORDER BY last_updated DESC")
        remaining_threads = [row[0] for row in cursor.fetchall()]
        expected_threads = [f"test_thread_{i}" for i in range(3)]
        self.assertEqual(remaining_threads, expected_threads)

if __name__ == '__main__':
    unittest.main() 