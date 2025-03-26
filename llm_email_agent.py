#!/usr/bin/env python3
"""
LLM Email Review Agent

This script allows LLMs (like Claude) to access and analyze emails from the Supabase database,
especially those marked as requiring a response. It combines regular database queries with
vector similarity search to provide rich context for analysis.

Usage:
  python llm_email_agent.py [command] [options]

Examples:
  python llm_email_agent.py review                   # Review emails marked as "respond"
  python llm_email_agent.py review --category notify # Review emails marked as "notify"
  python llm_email_agent.py search "contract review" # Search emails by similarity
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import openai

# Load environment variables
load_dotenv()

# Get Supabase credentials
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
openai_api_key = os.environ.get("OPENAI_API_KEY")

if not supabase_url or not supabase_key:
    print("Error: Supabase credentials not found in environment variables")
    print("Make sure the .env file contains SUPABASE_URL and SUPABASE_KEY")
    sys.exit(1)

if not openai_api_key:
    print("Warning: OpenAI API key not found. Vector search functionality will be limited.")

# Initialize clients
supabase: Client = create_client(supabase_url, supabase_key)
openai.api_key = openai_api_key

def format_date(date_string):
    """Format date string to a more readable format"""
    try:
        if isinstance(date_string, str):
            if 'Z' in date_string:
                date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            elif '+' in date_string:
                date_obj = datetime.fromisoformat(date_string)
            else:
                date_obj = datetime.fromisoformat(date_string + "+00:00")
        else:
            return date_string
        return date_obj.strftime("%b %d, %Y at %I:%M %p")
    except Exception as e:
        return date_string

def get_emails_by_category(category="respond", limit=5, offset=0) -> List[Dict[str, Any]]:
    """
    Get emails from a specific category
    
    Args:
        category: Email category (respond, notify, done)
        limit: Maximum number of emails to return
        offset: Pagination offset
        
    Returns:
        List of email dictionaries
    """
    try:
        query = supabase.table("emails").select("*").eq("category", category)
        query = query.order("received_date", desc=True)
        query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Error fetching emails by category: {e}")
        return []

def get_similar_emails(query_text: str, limit=3) -> List[Dict[str, Any]]:
    """
    Find emails similar to a query using vector similarity search
    
    Args:
        query_text: Text to search for
        limit: Maximum number of results
        
    Returns:
        List of similar emails
    """
    try:
        # Generate embedding for the query
        embedding_response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=query_text
        )
        embedding = embedding_response.data[0].embedding
        
        # Try to use the rpc function if it exists
        try:
            similar_response = supabase.rpc(
                "match_email_sections",
                {"query_embedding": embedding, "match_threshold": 0.5, "match_count": limit}
            ).execute()
            
            if similar_response.data:
                # Get full email details for the matched sections
                email_ids = list(set([item["email_id"] for item in similar_response.data]))
                
                email_query = supabase.table("emails").select("*").in_("id", email_ids)
                email_response = email_query.execute()
                
                return email_response.data
        except Exception as rpc_error:
            print(f"RPC search failed, falling back to basic search: {rpc_error}")
            
        # Fallback to getting recent emails if vector search not available
        recent_response = supabase.table("emails").select(
            "*"
        ).order("received_date", desc=True).limit(limit).execute()
        
        return recent_response.data
            
    except Exception as e:
        print(f"Error performing similarity search: {e}")
        return []

def format_email_for_llm(email: Dict[str, Any]) -> str:
    """
    Format an email for LLM consumption
    
    Args:
        email: Email dictionary
        
    Returns:
        Formatted email string
    """
    formatted = f"""
EMAIL_ID: {email.get('id', 'Unknown')}
SUBJECT: {email.get('subject', 'No Subject')}
FROM: {email.get('sender', 'Unknown Sender')}
TO: {', '.join(email.get('recipient', [])) if isinstance(email.get('recipient'), list) else email.get('recipient', 'Unknown Recipient')}
DATE: {format_date(email.get('received_date', ''))}
CATEGORY: {email.get('category', 'Unknown')}

BODY:
{email.get('body', 'No content')}
"""
    return formatted

def format_emails_for_llm(emails: List[Dict[str, Any]]) -> str:
    """
    Format multiple emails for LLM consumption
    
    Args:
        emails: List of email dictionaries
        
    Returns:
        Formatted emails string
    """
    if not emails:
        return "No emails found."
    
    formatted_emails = []
    for i, email in enumerate(emails):
        formatted = f"--- EMAIL {i+1} ---\n" + format_email_for_llm(email)
        formatted_emails.append(formatted)
    
    return "\n\n".join(formatted_emails)

def get_email_context(email_id: int) -> Dict[str, Any]:
    """
    Get context for an email including related emails
    
    Args:
        email_id: ID of the email
        
    Returns:
        Dictionary with email and context
    """
    try:
        # Get the primary email
        email_response = supabase.table("emails").select("*").eq("id", email_id).single().execute()
        if not email_response.data:
            return {"error": f"Email with ID {email_id} not found"}
        
        email = email_response.data
        
        # Find similar emails if possible
        similar_emails = []
        if email.get('body'):
            try:
                # Look for emails with the same sender
                sender_emails = supabase.table("emails").select("*").eq("sender", email.get('sender')).neq("id", email