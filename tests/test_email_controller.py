import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from controllers.email_controller import EmailController
from email_conversation_manager.types import EmailConversationState, ChatMessage

class TestEmailController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.controller = EmailController()
        # Mock the dependencies
        self.controller.gmail_service = Mock()
        self.controller.delivery_manager = Mock()
        self.controller.state_repository = Mock()

    def test_process_input_new_conversation(self):
        """Test processing a new email conversation."""
        # Test data
        email_data = {
            'id': 'test_msg_id',
            'threadId': 'test_thread_id'
        }
        
        # Mock email details
        mock_email_details = {
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'From', 'value': 'test@example.com'}
                ],
                'body': {'data': 'Test email body'}
            }
        }
        
        # Mock the gmail service responses
        self.controller.gmail_service.authenticate_gmail.return_value = 'mock_service'
        self.controller.gmail_service.get_email_details.return_value = mock_email_details
        self.controller.gmail_service.parse_email_details.return_value = {
            'sender_email': 'test@example.com',
            'sender_name': 'Test User',
            'body': 'Test email body'
        }
        
        # Mock conversation app response
        mock_final_state = EmailConversationState(
            thread_id='test_thread_id',
            last_updated=datetime.now().isoformat(),
            user_input='Test email body',
            user_email='test@example.com',
            user_name='Test User',
            appended_chat_history=[],
            previous_chat_history=[],
            classified_intent=None,
            available_slots=None,
            booked_slot=None,
            generated_response='Test response',
            error_message=None,
            booking_link=None,
            event_type_slug=None
        )
        
        with patch('controllers.email_controller.conversation_app') as mock_conversation_app:
            mock_conversation_app.invoke.return_value = mock_final_state
            
            # Execute the method
            self.controller.process_input(email_data)
            
            # Verify the calls
            self.assertEqual(self.controller.gmail_service.authenticate_gmail.call_count, 2)
            self.controller.gmail_service.get_email_details.assert_called_once()
            self.controller.gmail_service.parse_email_details.assert_called_once()
            mock_conversation_app.invoke.assert_called_once()
            self.controller.state_repository.save_state.assert_called_once()
            self.controller.delivery_manager.send_email_response.assert_called_once()

    def test_process_input_existing_conversation(self):
        """Test processing a reply to an existing conversation."""
        # Test data
        email_data = {
            'id': 'test_msg_id',
            'threadId': 'test_thread_id'
        }
        
        # Create a chat message for the previous conversation
        previous_message = ChatMessage(
            role='user',
            content='Previous conversation'
        )
        
        # Mock existing state
        existing_state = EmailConversationState(
            thread_id='test_thread_id',
            last_updated=datetime.now().isoformat(),
            user_input='Previous message',
            user_email='test@example.com',
            user_name='Test User',
            appended_chat_history=[],
            previous_chat_history=[previous_message],
            classified_intent=None,
            available_slots=None,
            booked_slot=None,
            generated_response=None,
            error_message=None,
            booking_link=None,
            event_type_slug=None
        )
        
        # Mock email details
        mock_email_details = {
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'From', 'value': 'test@example.com'}
                ],
                'body': {'data': 'Test reply body'}
            }
        }
        
        # Mock the gmail service responses
        self.controller.gmail_service.authenticate_gmail.return_value = 'mock_service'
        self.controller.gmail_service.get_email_details.return_value = mock_email_details
        self.controller.gmail_service.parse_email_details.return_value = {
            'sender_email': 'test@example.com',
            'sender_name': 'Test User',
            'body': 'Test reply body'
        }
        
        # Mock state repository
        self.controller.state_repository.get_state.return_value = existing_state
        
        # Mock conversation app response
        mock_final_state = EmailConversationState(
            thread_id='test_thread_id',
            last_updated=datetime.now().isoformat(),
            user_input='Test reply body',
            user_email='test@example.com',
            user_name='Test User',
            appended_chat_history=[],
            previous_chat_history=[previous_message],
            classified_intent=None,
            available_slots=None,
            booked_slot=None,
            generated_response='Test response',
            error_message=None,
            booking_link=None,
            event_type_slug=None
        )
        
        with patch('controllers.email_controller.conversation_app') as mock_conversation_app:
            mock_conversation_app.invoke.return_value = mock_final_state
            
            # Execute the method
            self.controller.process_input(email_data)
            
            # Verify the calls
            self.controller.state_repository.get_state.assert_called_once_with('test_thread_id')
            mock_conversation_app.invoke.assert_called_once()
            self.controller.state_repository.save_state.assert_called_once()
            self.controller.delivery_manager.send_email_response.assert_called_once()

    def test_cleanup_old_conversations(self):
        """Test cleaning up old conversations."""
        # Mock active conversations
        mock_conversations = [
            EmailConversationState(
                thread_id='thread1',
                last_updated=datetime.now().isoformat(),
                user_input='Test message 1',
                user_email='test1@example.com',
                user_name='Test User 1',
                appended_chat_history=[],
                previous_chat_history=[],
                classified_intent=None,
                available_slots=None,
                booked_slot=None,
                generated_response=None,
                error_message=None,
                booking_link=None,
                event_type_slug=None
            ),
            EmailConversationState(
                thread_id='thread2',
                last_updated=datetime.now().isoformat(),
                user_input='Test message 2',
                user_email='test2@example.com',
                user_name='Test User 2',
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
        ]
        self.controller.state_repository.list_active_conversations.return_value = mock_conversations
        
        # Execute the method
        self.controller.cleanup_old_conversations(days=30)
        
        # Verify the calls
        self.controller.state_repository.list_active_conversations.assert_called_once_with(30)
        self.assertEqual(
            self.controller.state_repository.delete_state.call_count,
            2
        )

if __name__ == '__main__':
    unittest.main() 