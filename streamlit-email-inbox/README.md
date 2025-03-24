# Law Firm Email Inbox UI

A Streamlit-based front-end UI for managing and responding to emails with AI assistance.

## Overview

This application provides a user-friendly interface for managing emails stored in a Supabase database. It allows for:

- Viewing emails by category (All, Active, Respond, Notify, Done)
- Reading email content
- Interacting with a Law Firm chatbot to help draft responses
- Marking emails as "done" once processed

The application integrates with an existing email categorization system and a Law Firm chatbot.

## Features

- **Email Listing**: View emails in an inbox-like interface with pagination
- **Category Filters**: Filter emails by different categories
- **Email Viewer**: Read the full content of selected emails
- **Chatbot Integration**: Chat with a Law Firm AI assistant about the selected email
- **Response Generation**: Generate draft email responses with AI assistance
- **Email Management**: Mark emails as "done" after processing

## Setup

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up the environment variables in `.env`:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   ```

3. Run the Streamlit application:
   ```bash
   streamlit run app.py
   ```

## Integration with Existing Systems

### Email Database

The application connects to a Supabase database that contains emails with the following structure:
- `emails` table: Contains email metadata and content
- Email categories: "respond", "notify", "done"

### Chatbot Integration

The application includes a placeholder for integrating with your existing Law Firm chatbot. To use your actual chatbot:

1. Modify the `chatbot_integration.py` file to connect with your chatbot system
2. Implement the `get_response` and `generate_email_response` methods to use your actual chatbot

## Project Structure

- `app.py`: Main Streamlit application
- `supabase_utils.py`: Utilities for interacting with the Supabase database
- `chatbot_integration.py`: Integration with the Law Firm chatbot
- `requirements.txt`: Required Python dependencies

## Customization

- **UI Appearance**: Modify the Streamlit UI components in `app.py`
- **Email Processing Logic**: Customize the email processing workflows in `app.py`
- **Chatbot Integration**: Implement your chatbot connection in `chatbot_integration.py`
- **Database Queries**: Adjust the database interaction in `supabase_utils.py`

## Next Steps for Implementation

1. Update the `.env` file with your actual Supabase credentials
2. Integrate your existing Law Firm chatbot in `chatbot_integration.py`
3. Test the application with your actual email data
4. Deploy the Streamlit application to your preferred hosting environment
