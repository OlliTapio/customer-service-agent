# AI Receptionist Email Bot

This project is an AI-powered email assistant that automatically responds to customer inquiries and helps them book meetings.

## Project Setup (Windows)

1.  **Prerequisites:**
    *   Python 3.8+ installed.
    *   Google Workspace account (Business Starter or higher)
    *   Access to Google Cloud Platform and a project with Gmail API enabled.
    *   API key for Google Gemini.
    *   A Cal.com account for meeting bookings.
    *   (Optional) Voice functionality requires additional setup:
        - Google Cloud Speech-to-Text API enabled
        - Google Cloud Text-to-Speech API enabled
        - Appropriate API credentials configured

2.  **Google Workspace Setup:**
    *   Sign up for Google Workspace (Business Starter or higher)
    *   Create a new user account for the AI assistant (e.g., assistant@yourdomain.com)
    *   Set up email forwarding rules if needed
    *   Ensure the account has proper permissions for Gmail API access

3.  **Google Cloud Platform Setup:**
    *   Create a new project in Google Cloud Console
    *   Enable the following APIs:
        - Gmail API
        - Google Gemini API
        - (Optional) Cloud Speech-to-Text API
        - (Optional) Cloud Text-to-Speech API
    *   Create OAuth 2.0 credentials for Gmail API
    *   Download the credentials and save as `secrets/gmail_credentials.json`

4.  **Clone the Repository (if applicable):**
    ```bash
    git clone <your-repository-url>
    cd ai-receptionist
    ```

5.  **Create and Activate Virtual Environment:**
    Open PowerShell or Command Prompt in the project directory (`ai-receptionist`):
    ```powershell
    # Create the virtual environment
    python -m venv .venv

    # Activate the virtual environment (PowerShell)
    .venv\Scripts\Activate.ps1
    ```
    *(For Command Prompt, activation is `.venv\Scripts\activate.bat`)*
    Your terminal prompt should change to indicate the active virtual environment (e.g., `(.venv) PS C:\path\to\ai-receptionist>`).

6.  **Install Dependencies:**
    Once the virtual environment is created (and ideally activated in your local terminal), install the required packages using:
    ```bash
    # Ensure you are in the project root directory
    # If your venv is activated, you can just use: pip install -r requirements.txt
    # For more robustness, especially in scripts, call pip from the venv directly:
    .venv\Scripts\pip.exe install -r requirements.txt
    ```

7.  **Configuration:**
    - Place your Gmail OAuth credentials in `secrets/gmail_credentials.json` (see Google Cloud docs for format).
    - Create `secrets/credentials.json` with the following structure:
      ```json
      {
          "GOOGLE_GEMINI_API_KEY": "your-gemini-api-key",
          "CAL_COM_API_KEY": "your-cal-com-api-key"
      }
      ```
    - Edit `config.py` to update:
      - `ASSISTANT_EMAIL`: Set to your Google Workspace assistant email
      - `CAL_COM_USERNAME`: Your Cal.com username
      - `CAL_COM_EVENT_TYPE_SLUG`: Your meeting type slug
      - `SKIP_SENDING_EMAILS`: Set to `False` for production use
    - For voice functionality, ensure the following environment variables are set:
        - `GOOGLE_CLOUD_PROJECT`: Your Google Cloud project ID
        - `GOOGLE_APPLICATION_CREDENTIALS`: Path to your Google Cloud credentials file
        - `ENABLE_VOICE`: Set to "true" to enable voice functionality

## Running the Bot

```bash
python main.py
```
The bot will authenticate with Gmail, check for unread emails, and process them automatically.

---

## Testing

This project uses `pytest` for testing. To run all tests:

1. **Activate your virtual environment (if not already active):**
   ```powershell
   .venv\Scripts\Activate.ps1
   ```

2. **Run tests:**
   ```bash
   # Run all tests
   pytest
   
   # Run specific test categories
   pytest tests/test_state_service.py  # State management tests
   pytest tests/test_conversation_manager.py  # Conversation flow tests
   pytest tests/test_llm_service.py  # LLM service tests
   pytest tests/test_assistant.py  # Assistant integration tests
   ```
   This will discover and run all tests in the `tests/` directory.

   Note: Some tests require specific environment variables to be set. Check the test files for required variables.

---

## Development

When adding new packages, install them using `pip install <package-name>` (ideally in an activated venv) and then update the `requirements.txt` file. To ensure `requirements.txt` only captures venv packages:

```bash
# Ensure you are in the project root directory
# If your venv is activated, you can just use: pip freeze > requirements.txt
# For more robustness, call pip from the venv directly:
.venv\Scripts\pip.exe freeze > requirements.txt
```

## TODO / Next Steps

### Monday Deployment Plan
1. **Google Workspace Setup (Priority)**
   - [ ] Sign up for Google Workspace Business Starter
   - [ ] Create assistant@yourdomain.com account
   - [ ] Configure email forwarding rules
   - [ ] Set up proper Gmail API permissions

2. **Google Cloud Platform Configuration**
   - [ ] Create new GCP project
   - [ ] Enable required APIs:
     - Gmail API
     - Google Gemini API
   - [ ] Generate and download OAuth credentials
   - [ ] Set up proper IAM permissions

3. **Application Deployment**
   - [ ] Update config.py with new credentials
   - [ ] Test email sending functionality
   - [ ] Verify Cal.com integration
   - [ ] Deploy to production environment

### Future Development
- Prepare for production deployment on Google Cloud Platform (GCP):
  - Containerize the app (Dockerfile, requirements.txt, etc.)
  - Set up GCP Cloud Run or App Engine deployment
  - Configure environment variables and secrets for production
- Add webhook support for email threads (Gmail push notifications or polling)
- Create and configure a dedicated mailbox for the assistant email
- Harden error handling and logging for production
- Add more integration and end-to-end tests
- Update documentation for production setup and GCP deployment 
- Future Features:
  - Voice functionality integration:
    - Implement speech-to-text for voice messages
    - Add text-to-speech for voice responses
    - Support multiple languages
    - Implement voice message caching
    - Add voice quality metrics
    - Optimize voice processing performance