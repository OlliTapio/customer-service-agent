# AI Receptionist Email Bot

This project is an AI-powered email assistant that automatically responds to customer inquiries and helps them book meetings.

## Project Setup (Windows)

1.  **Prerequisites:**
    *   Python 3.8+ installed.
    *   Access to Google Cloud Platform and a project with Gmail API enabled.
    *   API key for Google Gemini.
    *   A Cal.com account for meeting bookings.

2.  **Clone the Repository (if applicable):**
    ```bash
    git clone <your-repository-url>
    cd ai-receptionist
    ```

3.  **Create and Activate Virtual Environment:**
    Open PowerShell or Command Prompt in the project directory (`ai-receptionist`):
    ```powershell
    # Create the virtual environment
    python -m venv .venv

    # Activate the virtual environment (PowerShell)
    .venv\Scripts\Activate.ps1
    ```
    *(For Command Prompt, activation is `.venv\Scripts\activate.bat`)*
    Your terminal prompt should change to indicate the active virtual environment (e.g., `(.venv) PS C:\path\to\ai-receptionist>`).

4.  **Install Dependencies:**
    Once the virtual environment is created (and ideally activated in your local terminal), install the required packages using:
    ```bash
    # Ensure you are in the project root directory
    # If your venv is activated, you can just use: pip install -r requirements.txt
    # For more robustness, especially in scripts, call pip from the venv directly:
    .venv\Scripts\pip.exe install -r requirements.txt
    ```

5.  **Configuration:**
    *(Details on `config.py` and credential files will go here.)*

## Running the Bot

*(Instructions on how to run `main.py` will go here.)*

## Development

When adding new packages, install them using `pip install <package-name>` (ideally in an activated venv) and then update the `requirements.txt` file. To ensure `requirements.txt` only captures venv packages:

```bash
# Ensure you are in the project root directory
# If your venv is activated, you can just use: pip freeze > requirements.txt
# For more robustness, call pip from the venv directly:
.venv\Scripts\pip.exe freeze > requirements.txt
``` 