# Work-Life Balance Manager

Track daily activities, monitor time allocation & energy levels, and receive automated email/Telegram reminders.

## Setup Instructions
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file from `.env.example` and fill in your credentials.
3. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```
4. Run the background scheduler (in a separate terminal):
   ```bash
   python scheduler.py
   ```
