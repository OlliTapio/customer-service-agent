# gmail_service.py

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request # Added this import
from googleapiclient.discovery import build
import os.path
import base64
from email.mime.text import MIMEText
import re # Added for parsing sender email
from typing import Any, Dict, List, Optional

import config # To get GMAIL_CREDENTIALS_PATH and ASSISTANT_EMAIL

# Define the SCOPES. If modifying these, delete the token.json file.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify' # Added modify for completeness, can be commented out if not used
]
TOKEN_PATH = 'token.json' # Stores the user's access and refresh tokens

def authenticate_gmail() -> Optional[Any]:
    """Authenticates with Gmail API and returns a service object."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_PATH, SCOPES)
            # Ensure flow.run_local_server uses an available port or handles errors
            creds = flow.run_local_server(port=0) 
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service

def get_unread_emails(service: Any) -> List[Dict[str, Any]]:
    """Gets a list of unread emails for the assistant's email address."""
    # Query will search for unread emails addressed to the assistant's email.
    query = f'is:unread to:{config.ASSISTANT_EMAIL}'
    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        return messages
    except Exception as e:
        print(f"An error occurred while fetching unread emails: {e}")
        return []

def send_email(service: Any, to_address: str, subject: str, message_text: str) -> Optional[Dict[str, Any]]:
    """Creates and sends an email from the authenticated user (potentially as an alias)."""
    try:
        mime_message = MIMEText(message_text)
        mime_message['to'] = to_address
        mime_message['subject'] = subject
        # For sending as an alias, ensure 'Send mail as' is configured in Gmail.
        # The API typically respects this if the From address is a configured alias.
        # mime_message['from'] = config.ASSISTANT_EMAIL 
        # Explicitly setting 'From'
        # Can be useful, but Gmail's behavior with aliases is key.

        raw_message = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()
        create_message = {'raw': raw_message}
        # Skip sending the email for now
        return create_message

        # message = service.users().messages().send(userId='me', body=create_message).execute()
        # print(f'Message Id: {message["id"]} sent to {to_address}')
        # return message
    except Exception as e:
        print(f'An error occurred while sending email: {e}')
        return None

def get_email_details(service: Any, message_id: str, format: str = 'full') -> Optional[Dict[str, Any]]:
    """Gets the full details of a specific email."""
    try:
        message = service.users().messages().get(userId='me', id=message_id, format=format).execute()
        return message
    except Exception as e:
        print(f'An error occurred while fetching email details for message ID {message_id}: {e}')
        return None

def mark_email_as_read(service: Any, message_id: str) -> bool:
    """Marks an email as read by removing the UNREAD label."""
    try:
        # To mark as read, we remove the 'UNREAD' label.
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Marked message {message_id} as read.")
        return True
    except Exception as e:
        print(f"An error occurred while marking email {message_id} as read: {e}")
        return False

def parse_email_details(message_payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Parses sender, subject, and body from email payload.

    Args:
        message_payload: The 'payload' part of a Gmail message resource.

    Returns:
        A dictionary with 'sender_name', 'sender_email', 'recipient_name', 'recipient_email', 'subject', and 'body', or None if parsing fails.
    """
    if not message_payload:
        return None

    headers = message_payload.get('headers', [])
    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
    
    # Parse From header
    from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
    from_match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>$', from_header)
    if from_match:
        sender_name = from_match.group(1).strip()
        sender_email = from_match.group(2)
    else:
        sender_name = ''
        sender_email = from_header.strip()
    
    # Parse To header
    to_header = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
    to_match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>$', to_header)
    if to_match:
        recipient_name = to_match.group(1).strip()
        recipient_email = to_match.group(2)
    else:
        recipient_name = ''
        recipient_email = to_header.strip()

    body = get_email_body_text(message_payload)

    return {
        'sender_name': sender_name,
        'sender_email': sender_email,
        'recipient_name': recipient_name,
        'recipient_email': recipient_email,
        'subject': subject,
        'body': body
    }

def get_email_body_text(message_payload: Dict[str, Any]) -> str:
    """Extracts the plain text body from an email message payload.
    Recursively searches through parts if it's a multipart email.
    """
    if not message_payload:
        return ""

    mime_type = message_payload.get('mimeType', '')
    body_data = message_payload.get('body', {}).get('data')

    if mime_type == 'text/plain' and body_data:
        return base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8', 'ignore')
    
    if mime_type.startswith('multipart/'):
        parts = message_payload.get('parts', [])
        text_body = ""
        html_body = ""
        for part in parts:
            part_mime_type = part.get('mimeType', '')
            part_body_data = part.get('body', {}).get('data')

            if part_mime_type == 'text/plain' and part_body_data:
                text_body += base64.urlsafe_b64decode(part_body_data.encode('ASCII')).decode('utf-8', 'ignore') + "\n"
            elif part_mime_type == 'text/html' and part_body_data:
                # We prefer text/plain, but will store html as a fallback if text/plain is empty
                html_body += base64.urlsafe_b64decode(part_body_data.encode('ASCII')).decode('utf-8', 'ignore') + "\n"
            elif part_mime_type.startswith('multipart/'):
                # Recursive call for nested multipart
                nested_body = get_email_body_text(part)
                if nested_body: # Prioritize text from nested parts
                    # This simple check doesn't distinguish deeply nested text/html vs text/plain well.
                    # For now, it just concatenates. A more robust parser might be needed for complex emails.
                    text_body += nested_body + "\n"


        # Prioritize plain text if available, otherwise use HTML (and strip tags later if needed)
        return text_body.strip() if text_body.strip() else html_body.strip()

    # Fallback for single part, non-text/plain (e.g. a single HTML part)
    if body_data: # if it's not multipart and has body data
        # This might be HTML or other content, decode as best effort
        try:
            return base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8', 'ignore')
        except Exception:
            return "[Could not decode body content]"
            
    return "" # No parsable content found

# Example Usage (for direct testing of this module)
if __name__ == '__main__':
    print("Attempting to authenticate with Gmail...")
    gmail_service = authenticate_gmail()
    if gmail_service:
        print("Successfully authenticated with Gmail.")

        # Test fetching unread emails
        print("\nFetching unread emails...")
        unread_messages = get_unread_emails(gmail_service)
        if not unread_messages:
            print(f"No unread emails found for {config.ASSISTANT_EMAIL}.")
        else:
            print(f"Found {len(unread_messages)} unread email(s) for {config.ASSISTANT_EMAIL}:")
            for msg_summary in unread_messages[:2]: # Process first 2 for brevity
                print(f"  Email ID: {msg_summary['id']}")
                msg_detail = get_email_details(gmail_service, msg_summary['id'], format='metadata')
                if msg_detail and msg_detail.get('payload'):
                    headers = msg_detail.get('payload').get('headers')
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'N/A')
                    from_sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'N/A')
                    print(f"    From: {from_sender}")
                    print(f"    Subject: {subject}")
                    print(f"    Snippet: {msg_detail.get('snippet', 'N/A')}")

                    # Test parsing full body
                    full_message_details = get_email_details(gmail_service, msg_summary['id'], format='full')
                    if full_message_details and full_message_details.get('payload'):
                        parsed_content = parse_email_details(full_message_details['payload'])
                        if parsed_content:
                            print(f"      Parsed Sender: {parsed_content['sender_name']} <{parsed_content['sender_email']}>")
                            print(f"      Parsed Subject: {parsed_content['subject']}")
                            print(f"      Parsed Body Preview: {parsed_content['body'][:200]}...") # Preview first 200 chars
                    
                    # mark_email_as_read(gmail_service, msg_summary['id']) # Uncomment to test marking as read

        # Test sending an email
        # Important: Change recipient to a test email you control.
        test_recipient = "example@gmail.com"
        test_subject = f"Test from AI Bot for {config.ASSISTANT_EMAIL}"
        test_body = f"Hello,\n\nThis is a test email from your AI assistant regarding {config.ASSISTANT_EMAIL}.\nYour booking link: {config.CAL_COM_LINK}\n\nThanks!"
        
        if "your_actual_test_address@example.com" == test_recipient:
            print("\nSkipping test email: Please update 'test_recipient' in gmail_service.py to your own test email address.")
        else:
            print(f"\nAttempting to send a test email to {test_recipient}...")
            send_email(gmail_service, test_recipient, test_subject, test_body)
    else:
        print("Gmail authentication failed. Please check credentials and OAuth consent.")