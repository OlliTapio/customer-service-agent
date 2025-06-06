import json
import os

CAL_COM_LINK = "cal.com/otl-4refod/30min"

# Paths for credentials files
SECRETS_FOLDER = "secrets"
GMAIL_CREDENTIALS_PATH = os.path.join(SECRETS_FOLDER, "gmail_credentials.json")
CREDENTIALS_PATH = os.path.join(SECRETS_FOLDER, "credentials.json")  # Updated to use secrets folder

# Email settings
ASSISTANT_EMAIL = "assistant@otl.fi"
SKIP_SENDING_EMAILS = True  # Change to False to send emails

GOOGLE_GEMINI_API_KEY = None

# Cal.com Settings
CAL_COM_API_KEY = None
CAL_COM_USERNAME = "otl-4refod" # Your Cal.com username
CAL_COM_EVENT_TYPE_SLUG = "30min" # The slug of your versatile 30-min meeting event type
# We'll add logic to load CAL_COM_API_KEY from environment or a dedicated credentials file later if preferred 
if os.path.exists(CREDENTIALS_PATH):
    try:
        with open(CREDENTIALS_PATH, 'r') as f:
            creds = json.load(f)
            GOOGLE_GEMINI_API_KEY = creds.get("GOOGLE_GEMINI_API_KEY")
            CAL_COM_API_KEY = creds.get("CAL_COM_API_KEY")
        if not GOOGLE_GEMINI_API_KEY:
            print(f"Warning: GOOGLE_GEMINI_API_KEY not found in {CREDENTIALS_PATH}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {CREDENTIALS_PATH}")
    except Exception as e:
        print(f"An error occurred while loading Gemini API key: {e}")
else:
    print(f"Warning: Gemini credentials file not found at {CREDENTIALS_PATH}. GOOGLE_GEMINI_API_KEY will be None.")

