# Intelligent Email Assistant Setup Guide

This guide explains how to set up and use the new intelligent email assistant features added to the Email Manager system.

## Overview

The intelligent email assistant automatically analyzes incoming emails marked as "respond", searches for relevant context in your email history, and provides proactive insights including:

- Summary and key points extraction
- Detection of payment references and dollar amounts
- Identification of case references and related emails
- Suggested responses and follow-up questions
- Detection of inconsistencies or important details

## Setup Steps

### 1. Update Database Schema

First, run the schema update script to add the necessary fields to your Supabase database:

```bash
cd /Users/aaronwhaley/Desktop/claude_desktop_docs/Email_Manager/scripts
python update_db_schema.py
```

This script adds:
- `processed_by_agent` field (Boolean) to track which emails have been analyzed
- `agent_analysis` field (JSON) to store the analysis results

### 2. Start the Email Assistant Agent

You can run the email assistant agent in monitor mode to continuously process new emails:

```bash
cd /Users/aaronwhaley/Desktop/claude_desktop_docs/Email_Manager
python email_assistant_agent.py monitor
```

Or you can process all pending emails once:

```bash
python email_assistant_agent.py process
```

### 3. Review Insights in the Streamlit Interface

The Streamlit interface has been updated to show assistant insights:

1. Start the Streamlit app:
   ```bash
   cd /Users/aaronwhaley/Desktop/claude_desktop_docs/Email_Manager
   docker-compose up -d
   ```

2. Access the interface at `http://localhost:8501`

3. Toggle the "Show assistant insights" option in the sidebar to enable/disable the feature

## Using the Email Assistant Agent

The email assistant agent can be used in three modes:

### 1. Monitor Mode

Continuously monitors for new "respond" emails and analyzes them automatically:

```bash
python email_assistant_agent.py monitor --interval 300
```

The `--interval` parameter specifies how often to check for new emails (in seconds).

### 2. Review Mode

Analyzes a specific email by ID:

```bash
python email_assistant_agent.py review 123
```

Replace `123` with the actual email ID you want to analyze.

### 3. Interactive Mode

Provides an interactive command-line interface to work with emails:

```bash
python email_assistant_agent.py interactive
```

Available commands in interactive mode:
- `list [category] [limit]` - List emails
- `review <id>` - Review a specific email
- `search <query>` - Search emails semantically
- `payments <sender>` - Search for payment references from a sender
- `process` - Process all unprocessed 'respond' emails
- `exit` - Exit interactive mode
- `help` - Show help message

## Configuration

The email assistant agent uses the following configuration from your `.env` file:

- `SUPABASE_URL` and `SUPABASE_KEY` - For database access
- `OPENAI_API_KEY` - For LLM and embedding generation

## Troubleshooting

If you encounter issues:

1. Check the logs for error messages
2. Ensure the database schema has been updated correctly
3. Verify that your API keys are valid
4. Try processing a single email in review mode to debug

## Example Workflow

1. New email arrives and is marked as "respond" by the triage system
2. Email assistant agent (running in monitor mode) detects the new email
3. Agent analyzes the email and searches for relevant context
4. Agent saves the analysis to the database
5. When you open the Streamlit interface, the email is marked with a 🧠 icon
6. You can view the assistant's insights to help craft your response

The agent helps you quickly understand the context, identify important details, and respond more effectively to emails.
