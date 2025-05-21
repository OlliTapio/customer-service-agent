import pytest
from unittest.mock import MagicMock
from services.gmail_service import parse_email_details

def test_parse_email_details():
    message_payload = {
        "headers": [
            {"name": "From", "value": "John Doe <john.doe@example.com>"},
            {"name": "Subject", "value": "Meeting Request"}
        ],
        "body": {"data": "SGVsbG8gdGhlcmU="}  # Base64 for "Hello there"
    }
    parsed_details = parse_email_details(message_payload)
    assert parsed_details["sender"] == "john.doe@example.com"
    assert parsed_details["subject"] == "Meeting Request"
    assert parsed_details["body"] == "Hello there"
