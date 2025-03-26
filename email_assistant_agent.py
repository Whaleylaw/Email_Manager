#!/usr/bin/env python3
"""
Intelligent Email Assistant Agent

This agent proactively analyzes emails marked as "respond" in the Supabase database,
searches for relevant context, and provides intelligent assistance including:
- Finding related prior conversations with the same sender
- Identifying referenced payments or important dates
- Detecting inconsistencies or important details
- Suggesting potential responses
- Formulating questions about how to proceed

The agent runs in three modes:
1. Monitor mode: Continuously checks for new "respond" emails
2. Review mode: Analyzes specific emails on demand
3. Interactive mode: Allows conversational interaction about an email

Usage:
  python email_assistant_agent.py monitor     # Continuously monitor for new emails
  python email_assistant_agent.py review ID   # Review a specific email by ID
  python email_assistant_agent.py interactive # Start an interactive session
"""

import os
import sys
import json
import time
import argparse
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import openai
import re
import html2text

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
    print("Error: OpenAI API key not found. Required for LLM integration.")
    sys.exit(1)

# Initialize clients
supabase: Client = create_client(supabase_url, supabase_key)
openai.api_key = openai_api_key

# HTML to Text converter
html_converter = html2text.HTML2Text()
html_converter.ignore_links = False
html_converter.body_width = 0  # No wrapping

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

def clean_html_content(html_content):
    """Convert HTML to readable text"""
    if not html_content:
        return ""
    return html_converter.handle(str(html_content))

def extract_dollar_amounts(text):
    """Extract dollar amounts from text"""
    amounts = []
    # Pattern for dollar amounts like $1,000.00 or $500 or 1,000 dollars
    pattern = r'\$\s?([0-9,]+(\.[0-9]{1,2})?)|([0-9,]+)(\.[0-9]{1,2})?\s?(dollars|USD)'
    matches = re.finditer(pattern, text, re.IGNORECASE)
    
    for match in matches:
        # Clean the amount string (remove commas, etc.)
        amount_str = match.group(0).replace(',', '').replace('dollars', '').replace('USD', '').strip()
        # Extract just the number
        if '$' in amount_str:
            amount_str = amount_str.replace('$', '').strip()
        try:
            amount = float(amount_str)
            amounts.append(amount)
        except ValueError:
            continue
    
    return amounts

def extract_case_references(text):
    """Extract case references and matter numbers"""
    cases = []
    
    # Common case citation patterns
    case_patterns = [
        r'case\s+no\.?\s+([a-z0-9\-]+)', # Case No. 12345
        r'case\s+number\s+([a-z0-9\-]+)', # Case Number 12345
        r'matter\s+no\.?\s+([a-z0-9\-]+)', # Matter No. 12345
        r'([a-z0-9\-]+)\s+v\.?\s+([a-z0-9\-]+)', # Smith v. Jones
        r'docket\s+no\.?\s+([a-z0-9\-]+)' # Docket No. 12345
    ]
    
    for pattern in case_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            cases.append(match.group(0))
    
    return cases

def get_emails_by_category(category="respond", limit=5, offset=0, processed=None) -> List[Dict[str, Any]]:
    """
    Get emails from a specific category
    
    Args:
        category: Email category (respond, notify, done)
        limit: Maximum number of emails to return
        offset: Pagination offset
        processed: Filter by processed status (True/False/None)
        
    Returns:
        List of email dictionaries
    """
    try:
        query = supabase.table("emails").select("*").eq("category", category)
        
        # Filter by processed status if specified
        if processed is not None:
            query = query.eq("processed_by_agent", processed)
        
        query = query.order("received_date", desc=True)
        query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Error fetching emails by category: {e}")
        return []

def mark_email_processed(email_id, analysis_result):
    """Mark an email as processed by the agent with analysis results"""
    try:
        response = supabase.table("emails").update({
            "processed_by_agent": True,
            "agent_analysis": json.dumps(analysis_result)
        }).eq("id", email_id).execute()
        return True
    except Exception as e:
        print(f"Error marking email as processed: {e}")
        return False

def get_email_by_id(email_id):
    """Get an email by its ID"""
    try:
        response = supabase.table("emails").select("*").eq("id", email_id).single().execute()
        return response.data
    except Exception as e:
        print(f"Error getting email by ID: {e}")
        return None

def get_emails_by_sender(sender, exclude_id=None, limit=5):
    """Get previous emails from the same sender"""
    try:
        query = supabase.table("emails").select("*").eq("sender", sender)
        
        if exclude_id:
            query = query.neq("id", exclude_id)
        
        query = query.order("received_date", desc=True).limit(limit)
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Error getting emails by sender: {e}")
        return []

def perform_semantic_search(query_text, limit=5):
    """Perform semantic search in the email vector database"""
    try:
        # Generate embedding for the query
        embedding_response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=query_text
        )
        embedding = embedding_response.data[0].embedding
        
        # Try to use the vector search RPC function
        try:
            similar_response = supabase.rpc(
                "match_email_sections",
                {"query_embedding": embedding, "match_threshold": 0.6, "match_count": limit*2}
            ).execute()
            
            if similar_response.data:
                # Get full email details for the matched sections
                email_ids = list(set([item["email_id"] for item in similar_response.data]))
                if len(email_ids) > limit:
                    email_ids = email_ids[:limit]
                    
                email_query = supabase.table("emails").select("*").in_("id", email_ids)
                email_response = email_query.execute()
                
                return email_response.data
        except Exception as rpc_error:
            print(f"RPC vector search failed: {rpc_error}")
            
        # Fallback to keyword search if vector search not available
        keywords = query_text.split()
        # Use ILIKE to search case-insensitively in the body or subject
        fallback_query = supabase.table("emails").select("*")
        
        # Add OR conditions for each keyword
        for keyword in keywords[:3]:  # Limit to first 3 keywords to avoid query complexity
            if len(keyword) > 3:  # Only use keywords of sufficient length
                fallback_query = fallback_query.or_(f"body.ilike.%{keyword}%,subject.ilike.%{keyword}%")
        
        fallback_response = fallback_query.limit(limit).execute()
        return fallback_response.data
            
    except Exception as e:
        print(f"Error performing semantic search: {e}")
        return []

def search_for_payment_references(sender, amount=None):
    """
    Search for payment references related to a sender
    
    Args:
        sender: Email sender to search for
        amount: Optional amount to specifically search for
    
    Returns:
        List of emails with payment references
    """
    payment_keywords = ["payment", "paid", "invoice", "billing", "fee", "deposit", "retainer", "cost"]
    
    # Construct a search query that looks for payment-related terms and the sender
    search_terms = " ".join(payment_keywords)
    if amount:
        search_terms += f" ${amount}"
    
    # First try vector search
    emails = perform_semantic_search(f"{search_terms} from {sender}", limit=10)
    
    # Filter results to only include emails that have dollar amounts
    payment_emails = []
    for email in emails:
        email_body = email.get('body', '')
        if not isinstance(email_body, str):
            continue
            
        # Clean HTML if necessary
        clean_body = clean_html_content(email_body)
        
        # Extract dollar amounts
        amounts = extract_dollar_amounts(clean_body)
        
        if amounts:
            email["extracted_amounts"] = amounts
            payment_emails.append(email)
    
    return payment_emails

def analyze_email_context(email, detailed=True):
    """
    Analyze an email and gather context to provide intelligent assistance
    
    Args:
        email: The email dict to analyze
        detailed: Whether to perform detailed analysis
        
    Returns:
        Analysis results dictionary
    """
    email_id = email.get('id')
    subject = email.get('subject', '')
    sender = email.get('sender', '')
    body = email.get('body', '')
    received_date = email.get('received_date', '')
    
    # Clean the body if it contains HTML
    clean_body = clean_html_content(body)
    
    # Initialize analysis results
    analysis = {
        "email_id": email_id,
        "subject": subject,
        "sender": sender,
        "received_date": format_date(received_date),
        "key_points": [],
        "related_emails": [],
        "payment_references": [],
        "case_references": extract_case_references(clean_body),
        "dollar_amounts": extract_dollar_amounts(clean_body),
        "suggested_responses": [],
        "questions": [],
        "summary": ""
    }
    
    print(f"Analyzing email from {sender}: {subject}")
    
    # Get previous conversations with the same sender
    previous_emails = get_emails_by_sender(sender, exclude_id=email_id, limit=5)
    if previous_emails:
        analysis["related_emails"] = [{
            "id": e.get('id'),
            "subject": e.get('subject'),
            "date": format_date(e.get('received_date')),
            "summary": clean_html_content(e.get('body', ''))[:200] + "..." if len(e.get('body', '')) > 200 else clean_html_content(e.get('body', ''))
        } for e in previous_emails]
    
    # If dollar amounts are mentioned, search for payment references
    if analysis["dollar_amounts"]:
        print(f"Found dollar amounts: {analysis['dollar_amounts']}")
        payment_emails = search_for_payment_references(sender)
        if payment_emails:
            analysis["payment_references"] = [{
                "id": e.get('id'),
                "subject": e.get('subject'),
                "date": format_date(e.get('received_date')),
                "amounts": e.get('extracted_amounts', []),
                "excerpt": clean_html_content(e.get('body', ''))[:200] + "..." if len(e.get('body', '')) > 200 else clean_html_content(e.get('body', ''))
            } for e in payment_emails]
    
    # If case references are found, look for related case discussions
    if analysis["case_references"]:
        print(f"Found case references: {analysis['case_references']}")
        for case_ref in analysis["case_references"]:
            case_emails = perform_semantic_search(case_ref, limit=3)
            for e in case_emails:
                if e.get('id') != email_id:
                    analysis["related_emails"].append({
                        "id": e.get('id'),
                        "subject": e.get('subject'),
                        "date": format_date(e.get('received_date')),
                        "relevance": f"Related to case {case_ref}",
                        "summary": clean_html_content(e.get('body', ''))[:200] + "..." if len(e.get('body', '')) > 200 else clean_html_content(e.get('body', ''))
                    })
    
    # If detailed analysis requested, use LLM to extract key points and generate suggestions
    if detailed:
        # Prepare context for the LLM
        email_context = {
            "email": {
                "id": email_id,
                "subject": subject,
                "sender": sender,
                "body": clean_body,
                "received_date": format_date(received_date)
            },
            "previous_emails": [{
                "id": e.get('id'),
                "subject": e.get('subject'),
                "body": clean_html_content(e.get('body', '')),
                "date": format_date(e.get('received_date'))
            } for e in previous_emails[:3]], # Limit to 3 for token considerations
            "payment_references": analysis["payment_references"],
            "case_references": analysis["case_references"],
            "dollar_amounts": analysis["dollar_amounts"]
        }
        
        # Generate LLM prompt
        prompt = f"""
You are an intelligent legal assistant for a law firm. Your job is to review emails and provide helpful analysis.

Please analyze this email and the provided context, then extract:
1. Key points that require attention or action
2. Any inconsistencies or important details (especially regarding payments, dates, or case references)
3. Suggested responses or approaches
4. Questions to ask to gather more information if needed
5. A brief summary of what this email is about

The email and context are provided in JSON format:
{json.dumps(email_context, indent=2)}

Provide your analysis in a structured JSON format with these fields:
- key_points: array of strings
- inconsistencies: array of strings
- suggested_responses: array of strings
- questions: array of strings
- summary: string

Only include information that is relevant and helpful. Be concise but thorough.
"""

        try:
            # Call OpenAI API for analysis
            response = openai.chat.completions.create(
                model="gpt-4-turbo", 
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            llm_analysis = json.loads(response.choices[0].message.content)
            
            # Update our analysis with LLM results
            analysis.update({
                "key_points": llm_analysis.get("key_points", []),
                "inconsistencies": llm_analysis.get("inconsistencies", []),
                "suggested_responses": llm_analysis.get("suggested_responses", []),
                "questions": llm_analysis.get("questions", []),
                "summary": llm_analysis.get("summary", "")
            })
            
        except Exception as e:
            print(f"Error in LLM analysis: {e}")
            analysis["analysis_error"] = str(e)
    
    return analysis

def process_new_emails(limit=5):
    """Process new unprocessed emails marked as 'respond'"""
    # Get unprocessed respond emails
    emails = get_emails_by_category(category="respond", limit=limit, processed=False)
    
    if not emails:
        print("No new 'respond' emails to process.")
        return []
    
    print(f"Processing {len(emails)} new 'respond' emails...")
    
    results = []
    for email in emails:
        # Analyze the email
        analysis = analyze_email_context(email)
        
        # Mark as processed
        success = mark_email_processed(email.get('id'), analysis)
        
        if success:
            print(f"Successfully processed email ID {email.get('id')}")
            results.append(analysis)
        else:
            print(f"Failed to mark email ID {email.get('id')} as processed")
    
    return results

def format_analysis_for_display(analysis):
    """Format analysis results for command-line display"""
    divider = "="*80
    
    display = f"\n{divider}\n"
    display += f"EMAIL: {analysis.get('subject')}\n"
    display += f"FROM: {analysis.get('sender')}\n"
    display += f"DATE: {analysis.get('received_date')}\n"
    display += f"{divider}\n\n"
    
    # Summary
    display += f"SUMMARY:\n{analysis.get('summary', 'No summary available.')}\n\n"
    
    # Key points
    display += "KEY POINTS:\n"
    for point in analysis.get('key_points', []):
        display += f"• {point}\n"
    if not analysis.get('key_points'):
        display += "• No key points identified.\n"
    display += "\n"
    
    # Inconsistencies
    if 'inconsistencies' in analysis and analysis['inconsistencies']:
        display += "INCONSISTENCIES/IMPORTANT DETAILS:\n"
        for item in analysis['inconsistencies']:
            display += f"• {item}\n"
        display += "\n"
    
    # Dollar amounts
    if analysis.get('dollar_amounts'):
        display += "DOLLAR AMOUNTS MENTIONED:\n"
        for amount in analysis.get('dollar_amounts', []):
            display += f"• ${amount:.2f}\n"
        display += "\n"
    
    # Payment references
    if analysis.get('payment_references'):
        display += "RELATED PAYMENT REFERENCES:\n"
        for ref in analysis.get('payment_references', []):
            display += f"• {ref.get('date')} - {ref.get('subject')} - Amounts: {', '.join(['$' + str(amt) for amt in ref.get('amounts', [])])}\n"
        display += "\n"
    
    # Case references
    if analysis.get('case_references'):
        display += "CASE REFERENCES:\n"
        for case in analysis.get('case_references', []):
            display += f"• {case}\n"
        display += "\n"
    
    # Related emails
    if analysis.get('related_emails'):
        display += "RELATED PREVIOUS EMAILS:\n"
        for email in analysis.get('related_emails', []):
            relevance = f" - {email.get('relevance')}" if 'relevance' in email else ""
            display += f"• {email.get('date')} - {email.get('subject')}{relevance}\n"
        display += "\n"
    
    # Suggested responses
    display += "SUGGESTED RESPONSES:\n"
    for response in analysis.get('suggested_responses', []):
        display += f"• {response}\n"
    if not analysis.get('suggested_responses'):
        display += "• No suggested responses available.\n"
    display += "\n"
    
    # Questions
    display += "QUESTIONS TO CONSIDER:\n"
    for question in analysis.get('questions', []):
        display += f"• {question}\n"
    if not analysis.get('questions'):
        display += "• No questions identified.\n"
    
    display += f"\n{divider}\n"
    return display

def monitor_mode(check_interval=300):
    """
    Monitor mode: continuously check for new 'respond' emails
    
    Args:
        check_interval: Time between checks in seconds (default: 5 minutes)
    """
    print(f"Starting monitor mode. Checking for new 'respond' emails every {check_interval} seconds.")
    print("Press Ctrl+C to exit.")
    
    try:
        while True:
            print(f"\nChecking for new emails at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
            results = process_new_emails()
            
            if results:
                print(f"Processed {len(results)} new emails:")
                for analysis in results:
                    print(format_analysis_for_display(analysis))
            
            print(f"Next check in {check_interval} seconds...")
            time.sleep(check_interval)
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"Error in monitor mode: {e}")

def review_mode(email_id):
    """
    Review mode: analyze a specific email by ID
    
    Args:
        email_id: ID of the email to review
    """
    print(f"Reviewing email ID: {email_id}")
    
    # Get the email
    email = get_email_by_id(email_id)
    
    if not email:
        print(f"Error: Email with ID {email_id} not found.")
        return
    
    # Analyze the email
    analysis = analyze_email_context(email)
    
    # Display the analysis
    print(format_analysis_for_display(analysis))
    
    # Optionally update the email as processed
    if email.get('processed_by_agent') is not True:
        response = input("Mark this email as processed by the agent? (y/n): ")
        if response.lower() == 'y':
            success = mark_email_processed(email_id, analysis)
            if success:
                print(f"Email ID {email_id} marked as processed.")
            else:
                print(f"Failed to mark Email ID {email_id} as processed.")

def interactive_mode():
    """Interactive mode: start an interactive session"""
    print("Starting interactive mode.")
    print("Type 'exit' to quit, 'help' for commands.")
    
    while True:
        command = input("\nEnter command: ").strip()
        
        if command.lower() == 'exit':
            print("Exiting interactive mode.")
            break
        
        elif command.lower() == 'help':
            print("\nAvailable commands:")
            print("  list [category] [limit]   - List emails (default: respond, limit 5)")
            print("  review <id>               - Review a specific email")
            print("  search <query>            - Search emails semantically")
            print("  payments <sender>         - Search for payment references from sender")
            print("  process                   - Process all unprocessed 'respond' emails")
            print("  exit                      - Exit interactive mode")
            print("  help                      - Show this help message")
        
        elif command.lower().startswith('list'):
            parts = command.split()
            category = parts[1] if len(parts) > 1 else "respond"
            limit = int(parts[2]) if len(parts) > 2 else 5
            
            emails = get_emails_by_category(category=category, limit=limit)
            
            if not emails:
                print(f"No emails found in category '{category}'.")
                continue
            
            print(f"\nFound {len(emails)} emails in category '{category}':")
            for i, email in enumerate(emails):
                processed = "✓" if email.get('processed_by_agent') else "✗"
                print(f"{i+1}. [{processed}] ID {email.get('id')} - {format_date(email.get('received_date'))} - {email.get('subject')}")
        
        elif command.lower().startswith('review'):
            parts = command.split()
            if len(parts) < 2:
                print("Error: Please specify an email ID to review.")
                continue
            
            try:
                email_id = int(parts[1])
                review_mode(email_id)
            except ValueError:
                print(f"Error: Invalid email ID '{parts[1]}'.")
        
        elif command.lower().startswith('search'):
            query = command[7:].strip()
            if not query:
                print("Error: Please specify a search query.")
                continue
            
            print(f"Searching for: {query}")
            results = perform_semantic_search(query)
            
            if not results:
                print("No results found.")
                continue
            
            print(f"\nFound {len(results)} results:")
            for i, email in enumerate(results):
                print(f"{i+1}. ID {email.get('id')} - {format_date(email.get('received_date'))} - {email.get('subject')}")
            
            while True:
                selection = input("\nEnter result number to review (or 'back'): ").strip()
                if selection.lower() == 'back':
                    break
                
                try:
                    index = int(selection) - 1
                    if 0 <= index < len(results):
                        review_mode(results[index].get('id'))
                        break
                    else:
                        print(f"Error: Please enter a number between 1 and {len(results)}.")
                except ValueError:
                    print("Error: Please enter a valid number.")
        
        elif command.lower().startswith('payments'):
            sender = command[9:].strip()
            if not sender:
                print("Error: Please specify a sender to search for payment references.")
                continue
            
            print(f"Searching for payment references from: {sender}")
            payment_emails = search_for_payment_references(sender)
            
            if not payment_emails:
                print("No payment references found.")
                continue
            
            print(f"\nFound {len(payment_emails)} payment references:")
            for i, email in enumerate(payment_emails):
                amounts = email.get('extracted_amounts', [])
                amount_str = ", ".join([f"${amount:.2f}" for amount in amounts])
                print(f"{i+1}. ID {email.get('id')} - {format_date(email.get('received_date'))} - {email.get('subject')} - Amounts: {amount_str}")
            
            while True:
                selection = input("\nEnter result number to review (or 'back'): ").strip()
                if selection.lower() == 'back':
                    break
                
                try:
                    index = int(selection) - 1
                    if 0 <= index < len(payment_emails):
                        review_mode(payment_emails[index].get('id'))
                        break
                    else:
                        print(f"Error: Please enter a number between 1 and {len(payment_emails)}.")
                except ValueError:
                    print("Error: Please enter a valid number.")
        
        elif command.lower() == 'process':
            results = process_new_emails()
            
            if not results:
                print("No new 'respond' emails to process.")
                continue
            
            print(f"Processed {len(results)} new emails:")
            for analysis in results:
                print(format_analysis_for_display(analysis))
        
        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands.")

def main():
    parser = argparse.ArgumentParser(description='Intelligent Email Assistant Agent')
    subparsers = parser.add_subparsers(dest='mode', help='Operating mode')
    
    # Monitor mode
    monitor_parser = subparsers.add_parser('monitor', help='Continuously monitor for new emails')
    monitor_parser.add_argument('--interval', type=int, default=300, help='Check interval in seconds')
    
    # Review mode
    review_parser = subparsers.add_parser('review', help='Review a specific email')
    review_parser.add_argument('email_id', type=int, help='Email ID to review')
    
    # Interactive mode
    interactive_parser = subparsers.add_parser('interactive', help='Start an interactive session')
    
    # Process mode (one-time processing of all unprocessed emails)
    process_parser = subparsers.add_parser('process', help='Process all unprocessed emails')
    process_parser.add_argument('--limit', type=int, default=10, help='Maximum number of emails to process')
    
    args = parser.parse_args()
    
    # Execute the selected mode
    if args.mode == 'monitor':
        monitor_mode(args.interval)
    elif args.mode == 'review':
        review_mode(args.email_id)
    elif args.mode == 'process':
        results = process_new_emails(args.limit)
        if results:
            print(f"Processed {len(results)} emails:")
            for analysis in results:
                print(format_analysis_for_display(analysis))
        else:
            print("No emails to process.")
    elif args.mode == 'interactive':
        interactive_mode()
    else:
        # Default to interactive mode if no mode specified
        interactive_mode()

if __name__ == "__main__":
    main()
