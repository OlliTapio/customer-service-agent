import pytest
from datetime import datetime, timedelta
from assistant.assistant import Assistant
from unittest.mock import patch, MagicMock
import os

# Sample available slots for testing
EXAMPLE_SLOTS = [
    {
        "time": "Monday, March 18, 2024 at 10:00 AM",
        "iso": "2024-03-18T10:00:00+02:00"
    },
    {
        "time": "Monday, March 18, 2024 at 2:00 PM",
        "iso": "2024-03-18T14:00:00+02:00"
    }
]

@pytest.fixture
def mock_cal_service():
    with patch('assistant.assistant.cal_service') as mock:
        # Mock get_event_type_details_v2
        mock.get_event_type_details_v2.return_value = {"id": "123"}
        
        # Mock get_available_slots_v1
        mock.get_available_slots_v1.return_value = [
            {"start": slot["iso"]} for slot in EXAMPLE_SLOTS
        ]
        
        # Mock create_booking
        mock.create_booking.return_value = True
        
        yield mock

@pytest.mark.integration
def test_booking_conversation(mock_cal_service):
    # Skip test if no API key is available
    if not os.getenv("GOOGLE_GEMINI_API_KEY"):
        pytest.skip("GOOGLE_GEMINI_API_KEY not set")
    
    # Initialize the assistant
    assistant = Assistant(
        customer_email="test@example.com",
    )
    
    # First message - asking for available times
    response1 = assistant.handle_conversation("""
Hello, 
Im interested to meet Olli, when is the next available time?
Best regards,
John Doe
""")
    assert "Monday, March 18, 2024 at 10:00 AM" in response1
    assert "Monday, March 18, 2024 at 2:00 PM" in response1