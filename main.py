# main.py
import time
import gmail_service
import llm_service
import cal_service
import config

def process_single_email(service, email_summary):
    """Processes a single email: gets details, generates reply, sends reply, marks as read."""
    msg_id = email_summary['id']
    print(f"\nProcessing email ID: {msg_id}...")

    email_details = gmail_service.get_email_details(service, msg_id, format='full')
    if not email_details or not email_details.get('payload'):
        print(f"Could not retrieve full details for email ID: {msg_id}")
        return

    parsed_info = gmail_service.parse_email_details(email_details.get('payload'))
    if not parsed_info or not parsed_info.get('body'):
        print(f"Could not parse body or essential details for email ID: {msg_id}")
        # Optionally mark as read or move to an error folder here if desired
        # gmail_service.mark_email_as_read(service, msg_id) 
        return

    sender_email = parsed_info['sender']
    original_subject = parsed_info['subject']
    email_body = parsed_info['body']

    print(f"  From: {sender_email}")
    print(f"  Subject: {original_subject}")
    # Prepare body snippet outside f-string to avoid backslash issue
    body_snippet = email_body[:100].replace('\n', ' ')
    print(f"  Body Snippet: {body_snippet}...")

    if not email_body.strip(): # Don't process empty emails
        print("  Email body is empty. Skipping LLM processing and marking as read.")
        gmail_service.mark_email_as_read(service, msg_id)
        return
        
    # Get the dynamic booking link from Cal.com service
    print("  Fetching Cal.com event details...")
    cal_event_details = cal_service.get_event_type_details(config.CAL_COM_EVENT_TYPE_SLUG)
    
    booking_link_to_use = None
    if cal_event_details and cal_event_details.get('booking_url'):
        booking_link_to_use = cal_event_details['booking_url']
        print(f"  Using dynamic Cal.com booking link: {booking_link_to_use}")
    else:
        print("  Warning: Could not fetch dynamic booking link from Cal.com. Falling back to static link from config.")
        # Fallback to the old static link from config if Cal.com API fails or event not found
        # This assumes you might want to keep a very basic link in config as a last resort.
        # For now, let's construct it similar to how cal_service does as a fallback.
        booking_link_to_use = f"https://cal.com/{config.CAL_COM_USERNAME}/{config.CAL_COM_EVENT_TYPE_SLUG}"
        print(f"  Using fallback static link: {booking_link_to_use}")

    # Generate response using LLM
    print("  Generating AI response...")
    ai_reply_text = llm_service.generate_email_response(email_body, booking_link_to_use, website_info="") 

    if not ai_reply_text or "I apologize, but I couldn't retrieve the specific booking link" in ai_reply_text:
        print(f"  Failed to generate AI response or booking link was missing. AI Response: {ai_reply_text}")
        # Decide if you want to mark as read, or leave unread for manual review, or send a generic error reply
        return

    # Prepare AI reply snippet outside f-string
    ai_reply_snippet = ai_reply_text[:100].replace('\n', ' ')
    print(f"  AI Reply Generated: {ai_reply_snippet}...")

    # Send the reply
    reply_subject = f"Re: {original_subject}"
    print(f"  Sending reply to: {sender_email} with subject: {reply_subject}")
    gmail_service.send_email(service, sender_email, reply_subject, ai_reply_text)

    # Mark original email as read
    gmail_service.mark_email_as_read(service, msg_id)
    print(f"Email ID: {msg_id} processed and marked as read.")

def main():
    print("Starting AI Email Assistant...")

    if not llm_service.llm_model:
        print("LLM Model not initialized. Please check Gemini API Key and llm_service.py. Exiting.")
        return
        
    print("Authenticating with Gmail...")
    gmail_api_service = gmail_service.authenticate_gmail()
    if not gmail_api_service:
        print("Gmail authentication failed. Please check credentials and OAuth consent. Exiting.")
        return
    print("Successfully authenticated with Gmail.")

    print(f"Checking for unread emails to {config.ASSISTANT_EMAIL}...")
    unread_emails = gmail_service.get_unread_emails(gmail_api_service)

    if not unread_emails:
        print("No unread emails found.")
    else:
        print(f"Found {len(unread_emails)} unread email(s).")
        for email_summary in unread_emails:
            try:
                process_single_email(gmail_api_service, email_summary)
                time.sleep(2) # Small delay between processing emails if you have many
            except Exception as e:
                print(f"An unexpected error occurred processing email ID {email_summary.get('id', 'N/A')}: {e}")
                # Optionally, implement more robust error handling here, like:
                # - Sending a notification to yourself
                # - Moving the problematic email to a specific folder/label
                # - Not marking as read so it can be manually reviewed

    print("\nAI Email Assistant run complete.")

if __name__ == '__main__':
    main() 