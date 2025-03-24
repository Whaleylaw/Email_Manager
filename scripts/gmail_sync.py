#!/usr/bin/env python3
import os
import email
import imaplib
import time
import sys
import random
from email.header import decode_header
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Add the parent directory to the path to import from libs
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the email triage agent
from email_triage_agent import EmailTriageFlow

# Load environment variables
load_dotenv()

# Configuration
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
gmail_email = os.environ.get("GMAIL_EMAIL")
gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

if not supabase_url or not supabase_key:
    print("Error: Supabase credentials not found in environment variables")
    sys.exit(1)
    
if not gmail_email or not gmail_password:
    print("Error: Gmail credentials not found in environment variables")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize Email Triage Flow
email_triage_flow = EmailTriageFlow()

def clean_email_address(addr):
    """Clean and extract email address."""
    if not addr:
        return ""
    
    # Handle format like "Name <email@example.com>"
    if '<' in addr and '>' in addr:
        start = addr.find('<') + 1
        end = addr.find('>')
        return addr[start:end].strip()
    return addr.strip()

def parse_email_addresses(addr_str):
    """Parse email addresses from comma-separated string."""
    if not addr_str:
        return []
    
    return [clean_email_address(addr) for addr in addr_str.split(',') if addr.strip()]

def decode_email_content(part):
    """Decode email content based on charset."""
    content = part.get_payload(decode=True)
    if not content:
        return ""
        
    charset = part.get_content_charset()
    
    if charset:
        try:
            return content.decode(charset)
        except:
            try:
                return content.decode('latin1')  # Fallback encoding
            except:
                return ""  # If all decoding fails
    else:
        try:
            return content.decode('utf-8')
        except:
            try:
                return content.decode('latin1')  # Fallback encoding
            except:
                return ""  # If all decoding fails

def get_email_body(msg):
    """Extract email body from a message object."""
    if msg.is_multipart():
        # If multipart, find the text part
        text_parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # Skip attachments
            if "attachment" in content_disposition:
                continue
            
            # Look for text/plain parts
            if content_type == "text/plain":
                try:
                    text_parts.append(decode_email_content(part))
                except:
                    continue
        
        # Join all text parts
        return "\n".join(text_parts)
    else:
        # Not multipart - return the payload directly
        try:
            return decode_email_content(msg)
        except:
            return ""

def get_last_sync_time():
    """Get the last sync time from the sync_status table."""
    try:
        response = supabase.table("sync_status").select("last_sync_time").eq("id", 1).execute()
        if response.data and len(response.data) > 0:
            last_sync = response.data[0]["last_sync_time"]
            # Handle different string formats
            if 'Z' in last_sync:
                return datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
            elif '+' in last_sync:
                return datetime.fromisoformat(last_sync)
            else:
                return datetime.fromisoformat(last_sync + "+00:00")
        else:
            # If no record exists, return a time 30 days ago
            return datetime.now() - timedelta(days=30)
    except Exception as e:
        print(f"Error getting last sync time: {e}")
        # Default to 30 days ago
        return datetime.now() - timedelta(days=30)

def update_last_sync_time():
    """Update the last sync time to now."""
    now = datetime.now().isoformat()
    try:
        supabase.table("sync_status").upsert({"id": 1, "last_sync_time": now}).execute()
    except Exception as e:
        print(f"Error updating last sync time: {e}")

def check_email_exists(gmail_id):
    """Check if an email with the given Gmail ID already exists in the database."""
    try:
        response = supabase.table("emails").select("id").eq("gmail_id", gmail_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking if email exists: {e}")
        return False

def triage_email(subject, body, sender):
    """
    Triage an email using the CrewAI agent
    
    Returns: 
        tuple: (category, reasoning)
    """
    # Log full email content for debugging
    print(f"\n========== EMAIL CONTENT ==========")
    print(f"Subject: {subject}")
    print(f"From: {sender}")
    print(f"Body: {body[:500]}... (truncated)")
    print(f"===================================\n")
    
    # Reset the flow state for a new email
    email_triage_flow.state.email_subject = subject
    email_triage_flow.state.email_body = body
    email_triage_flow.state.email_sender = sender
    
    # Run the triage flow
    try:
        # Add a small delay to prevent rate limiting with OpenAI
        time.sleep(random.uniform(0.5, 2.0))
        
        category = email_triage_flow.kickoff()
        reasoning = email_triage_flow.state.triage_reasoning
        
        # Double-check result - if category is not one of the valid options, default to notify
        if category not in ["ignore", "notify", "respond"]:
            print(f"WARNING: Invalid category '{category}', defaulting to 'notify'")
            category = "notify"
            reasoning += "\n[SYSTEM: Invalid category detected, defaulting to 'notify']"
        
        # Show detailed output for debugging
        print(f"\n========== TRIAGE RESULT ==========")
        print(f"CATEGORY: {category}")
        print(f"REASONING: {reasoning}")
        print(f"===================================\n")
        
        return category, reasoning
    except Exception as e:
        print(f"Error during email triage: {e}")
        # Default to 'notify' if triage fails
        return "notify", f"Triage failed with error: {str(e)}"

def fetch_emails(limit=None, unread_only=True, reprocess_all=False):
    """Fetch emails from Gmail via IMAP."""
    emails = []
    
    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail_email, gmail_password)
        
        # Force a connection reset to refresh IMAP status
        try:
            mail.close()
        except:
            pass
            
        mail.select("INBOX")  # Select inbox or another mailbox
        
        # Prepare search criteria - CRITICAL CHANGE: JUST USE 'UNSEEN' with no date filter
        if unread_only:
            search_criteria = 'UNSEEN'
        else:
            # A more flexible search that gets emails from the last 90 days
            ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime("%d-%b-%Y")
            search_criteria = f'SINCE "{ninety_days_ago}"'
            
        # If reprocessing all emails, look for all emails in a reasonable timeframe
        if reprocess_all:
            one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%d-%b-%Y")
            search_criteria = f'SINCE "{one_year_ago}"'
        
        print(f"Using search criteria: {search_criteria}")
        
        # Search for emails
        status, email_ids = mail.search(None, search_criteria)
        if status != 'OK':
            print(f"Error searching for emails: {status}")
            return emails
            
        email_id_list = email_ids[0].split()
        
        # Check if any emails were found
        if not email_id_list:
            print("No emails found matching the criteria.")
            return emails
        
        # Apply limit if specified
        if limit and limit < len(email_id_list):
            email_id_list = email_id_list[-limit:]  # Get most recent emails
        
        print(f"Found {len(email_id_list)} emails to process")
        
        # Get list of existing email IDs from the database
        existing_emails = set()
        try:
            response = supabase.table("emails").select("gmail_id").execute()
            if response.data:
                existing_emails = set(item["gmail_id"] for item in response.data)
                print(f"Found {len(existing_emails)} existing emails in database")
        except Exception as e:
            print(f"Error fetching existing emails: {e}")
        
        # Process each email
        for i, email_id in enumerate(email_id_list):
            print(f"Fetching email {i+1}/{len(email_id_list)} (ID: {email_id})")
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            
            if status != 'OK':
                print(f"Error fetching email {email_id}: {status}")
                continue
                
            for response in msg_data:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    
                    # Get subject
                    subject = ""
                    subject_header = decode_header(msg.get("Subject", ""))
                    for part, encoding in subject_header:
                        if isinstance(part, bytes):
                            if encoding:
                                try:
                                    subject += part.decode(encoding)
                                except:
                                    subject += part.decode('utf-8', errors='replace')
                            else:
                                subject += part.decode('utf-8', errors='replace')
                        else:
                            subject += str(part)
                    
                    # Get sender and recipients
                    sender = msg.get("From", "")
                    to = msg.get("To", "")
                    cc = msg.get("Cc", "")
                    bcc = msg.get("Bcc", "")
                    
                    # Get message ID
                    message_id = msg.get("Message-ID", "")
                    if not message_id:
                        # Generate a unique ID if none exists
                        message_id = f"generated-{email_id.decode()}-{time.time()}"
                    
                    # Ensure message_id is a string
                    if isinstance(message_id, bytes):
                        message_id = message_id.decode()
                    
                    # Clean < and > from message_id
                    message_id = message_id.strip("<>")
                    
                    # Skip if already in database (unless reprocessing)
                    if not reprocess_all and message_id in existing_emails:
                        print(f"Skipping already imported email: {subject[:50]}...")
                        continue
                    
                    # Get date
                    date_str = msg.get("Date", "")
                    try:
                        date = email.utils.parsedate_to_datetime(date_str)
                    except:
                        date = datetime.now()  # Fallback to current time
                    
                    # Get body
                    body = get_email_body(msg)
                    
                    # Triage the email using CrewAI
                    triage_category, triage_reasoning = triage_email(subject, body, sender)
                    
                    # Create email object with triage information
                    email_obj = {
                        "gmail_id": message_id,
                        "subject": subject,
                        "sender": sender,
                        "recipient": parse_email_addresses(to),
                        "cc": parse_email_addresses(cc),
                        "bcc": parse_email_addresses(bcc),
                        "body": body,
                        "date": date.isoformat(),
                        "category": triage_category,  # Add triage category
                        "triage_reasoning": triage_reasoning,  # Add triage reasoning
                        "reprocessed": message_id in existing_emails  # Flag for reprocessing
                    }
                    
                    emails.append(email_obj)
        
        # Close connection
        mail.close()
        mail.logout()
        
    except Exception as e:
        print(f"Error fetching emails: {e}")
    
    return emails

def store_emails(emails, reprocess_all=False):
    """Store emails in Supabase."""
    success_count = 0
    skip_count = 0
    fail_count = 0
    ignored_count = 0
    updated_count = 0
    
    for email in emails:
        try:
            # Check if this email is being reprocessed
            is_reprocessed = email.get("reprocessed", False)
            
            # Skip emails triaged as "ignore" (unless reprocessing)
            if email["category"] == "ignore" and not is_reprocessed:
                print(f"Ignoring email based on triage: {email['subject'][:50]}...")
                ignored_count += 1
                continue
            
            # If reprocessing, update existing record
            if is_reprocessed:
                response = supabase.table("emails").update({
                    "category": email["category"],
                    "triage_reasoning": email["triage_reasoning"][:1000]
                }).eq("gmail_id", email["gmail_id"]).execute()
                
                if response.data:
                    print(f"Updated email ({email['category']}): {email['subject'][:50]}...")
                    updated_count += 1
                else:
                    print(f"Failed to update email: {email['subject'][:50]}...")
                    fail_count += 1
            else:
                # Store as a new email
                response = supabase.table("emails").insert({
                    "subject": email["subject"],
                    "sender": email["sender"],
                    "recipient": email["recipient"],
                    "cc": email["cc"],
                    "bcc": email["bcc"],
                    "body": email["body"],
                    "gmail_id": email["gmail_id"],
                    "received_date": email["date"],
                    "category": email["category"],  # Add triage category to the database
                    "triage_reasoning": email["triage_reasoning"][:1000],  # Add triage reasoning (truncated if needed)
                    "processing_status": "pending"  # Set initial processing status
                }).execute()
                
                if response.data:
                    print(f"Stored email ({email['category']}): {email['subject'][:50]}...")
                    success_count += 1
                else:
                    print(f"Failed to store email: {email['subject'][:50]}...")
                    fail_count += 1
                
        except Exception as e:
            print(f"Error storing email: {e}")
            fail_count += 1
    
    if reprocess_all:
        return success_count, skip_count, fail_count, ignored_count, updated_count
    else:
        return success_count, skip_count, fail_count, ignored_count

def sync_gmail():
    """Sync new emails from Gmail since the last sync."""
    print("Starting Gmail sync...")
    
    # Fetch unread emails WITHOUT date filtering
    emails = fetch_emails(unread_only=True)
    print(f"Found {len(emails)} unread emails")
    
    # Store emails in Supabase
    success_count, skip_count, fail_count, ignored_count = store_emails(emails)
    
    # Update last sync time
    update_last_sync_time()
    
    print(f"Sync completed. Results: {success_count} imported, {skip_count} skipped, {ignored_count} ignored, {fail_count} failed")

def initial_import(limit=None, unread_only=True):
    """Perform initial import of emails."""
    print("Starting initial Gmail import...")
    
    # Fetch emails (with optional limit)
    emails = fetch_emails(limit=limit, unread_only=unread_only)
    print(f"Found {len(emails)} emails")
    
    # Store emails in Supabase
    success_count, skip_count, fail_count, ignored_count = store_emails(emails)
    
    # Update last sync time
    update_last_sync_time()
    
    print(f"Initial import completed. Results: {success_count} imported, {skip_count} skipped, {ignored_count} ignored, {fail_count} failed")

def reprocess_all_emails():
    """
    Reprocess all emails in the database with the current triage agent.
    This will update the category and reasoning for all emails.
    """
    print("Starting reprocessing of all emails...")
    
    # Fetch all emails from Gmail that match our database
    emails = fetch_emails(unread_only=False, reprocess_all=True)
    print(f"Found {len(emails)} emails to reprocess")
    
    # Update categories and reasoning in the database
    success_count, skip_count, fail_count, ignored_count, updated_count = store_emails(emails, reprocess_all=True)
    
    print(f"Reprocessing completed. Results: {success_count} new, {updated_count} updated, {skip_count} skipped, {ignored_count} ignored, {fail_count} failed")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync Gmail emails to Supabase with triage')
    parser.add_argument('--initial', action='store_true', help='Perform initial import')
    parser.add_argument('--limit', type=int, help='Limit number of emails to import')
    parser.add_argument('--all', action='store_true', help='Include all emails, not just unread (use with caution)')
    parser.add_argument('--reprocess-all', action='store_true', help='Reprocess all emails with current triage agent')
    parser.add_argument('--debug', action='store_true', help='Print additional debug information')
    
    args = parser.parse_args()
    
    # Print version info
    print("Gmail Sync with Email Triage v1.2")
    print(f"Options: initial={args.initial}, limit={args.limit}, all={args.all}, reprocess={args.reprocess_all}")
    
    # Determine if we should fetch all emails or just unread
    unread_only = not args.all
    
    # Check if we're reprocessing all emails
    if args.reprocess_all:
        reprocess_all_emails()
    elif args.initial:
        initial_import(limit=args.limit, unread_only=unread_only)
    else:
        sync_gmail()