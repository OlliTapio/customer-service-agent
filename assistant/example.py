import os
from assistant import Assistant

def main():
    # Initialize the assistant with your Cal.com credentials
    assistant = Assistant(
        api_key=os.getenv("CAL_COM_API_KEY"),
        username="your-username",  # Your Cal.com username
        event_type_slug="30min"    # Your default event type
    )
    
    # Example conversation
    user_email = "user@example.com"
    conversation_id = None
    
    # First message
    response = assistant.handle_message(
        message="Hi, I'd like to schedule a meeting to discuss your services.",
        user_email=user_email
    )
    print("Assistant:", response["response"])
    conversation_id = response["conversation_id"]
    
    # Follow-up message
    response = assistant.handle_message(
        message="Yes, Thursday at 2 PM works for me.",
        user_email=user_email,
        conversation_id=conversation_id
    )
    print("Assistant:", response["response"])

if __name__ == "__main__":
    main() 