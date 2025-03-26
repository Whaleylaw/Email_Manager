#!/usr/bin/env python3
"""
Supabase Database Viewer

This script connects to the Supabase database and displays its contents.
It reads the Supabase URL and API key from the .env file.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
from tabulate import tabulate
from datetime import datetime
import argparse

# Load environment variables
load_dotenv()

# Get Supabase credentials
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("Error: Supabase credentials not found in environment variables")
    print("Make sure the .env file contains SUPABASE_URL and SUPABASE_KEY")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

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
        # Format: Mar 23, 2025 at 10:30 AM
        return date_obj.strftime("%b %d, %Y at %I:%M %p")
    except Exception as e:
        return date_string

def truncate_text(text, max_length=100):
    """Truncate text to specified length"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def get_table_count(table_name):
    """Get the count of rows in a table"""
    try:
        response = supabase.table(table_name).select("id", count="exact").execute()
        return response.count
    except Exception as e:
        print(f"Error counting rows in {table_name}: {e}")
        return 0

def view_table(table_name, limit=10, offset=0, where=None, order_by=None):
    """View contents of a table with pagination"""
    try:
        # Start with a basic query
        query = supabase.table(table_name).select("*")
        
        # Apply filters if provided
        if where:
            field, value = where.split("=")
            query = query.eq(field.strip(), value.strip())
        
        # Apply ordering if provided
        if order_by:
            field, direction = order_by.split(":")
            query = query.order(field.strip(), desc=(direction.strip().lower() == "desc"))
        else:
            # Default ordering by id
            query = query.order("id")
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        # Execute the query
        response = query.execute()
        
        if not response.data:
            print(f"No data found in table '{table_name}'")
            return
        
        # Get total count for pagination info
        total_count = get_table_count(table_name)
        
        # Convert to a DataFrame for easier display
        df = pd.DataFrame(response.data)
        
        # Format dates and truncate long text fields
        for col in df.columns:
            if 'date' in col.lower() or col.lower() == 'created_at' or col.lower() == 'updated_at':
                df[col] = df[col].apply(format_date)
            elif df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: truncate_text(str(x)) if x is not None else "")
        
        # Display the data
        print(f"\n=== Table: {table_name} (showing {offset+1}-{min(offset+limit, total_count)} of {total_count}) ===\n")
        print(tabulate(df, headers="keys", tablefmt="pretty", showindex=False))
        
        return total_count, len(response.data)
    
    except Exception as e:
        print(f"Error viewing table '{table_name}': {e}")
        return 0, 0

def list_tables():
    """List all tables in the database"""
    try:
        # This is a simplified way to list tables
        # In a real Supabase environment, you might need to use a more specific approach
        tables = [
            "emails",
            "email_sections",
            "sync_status",
            # Add other known tables here
        ]
        
        print("\n=== Tables in Database ===\n")
        
        for table in tables:
            count = get_table_count(table)
            print(f"- {table} ({count} rows)")
        
        print("\nTo view a table, use: python view_database.py view <table_name>")
        
    except Exception as e:
        print(f"Error listing tables: {e}")

def view_emails_by_category(category, limit=10, offset=0):
    """View emails filtered by category"""
    try:
        # Start with a basic query
        query = supabase.table("emails").select("*")
        
        # Apply category filter
        query = query.eq("category", category)
        
        # Apply ordering by received_date
        query = query.order("received_date", desc=True)
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        # Execute the query
        response = query.execute()
        
        if not response.data:
            print(f"No emails found in category '{category}'")
            return
        
        # Get total count for pagination info
        count_response = supabase.table("emails").select("id", count="exact").eq("category", category).execute()
        total_count = count_response.count
        
        # Convert to a DataFrame for easier display
        df = pd.DataFrame(response.data)
        
        # Format dates and truncate long text fields
        for col in df.columns:
            if 'date' in col.lower() or col.lower() == 'created_at' or col.lower() == 'updated_at':
                df[col] = df[col].apply(format_date)
            elif df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: truncate_text(str(x)) if x is not None else "")
        
        # Display the data
        print(f"\n=== Emails in Category '{category}' (showing {offset+1}-{min(offset+limit, total_count)} of {total_count}) ===\n")
        
        # Select specific columns for display
        display_cols = ['id', 'subject', 'sender', 'received_date', 'category', 'processing_status']
        display_df = df[display_cols] if all(col in df.columns for col in display_cols) else df
        
        print(tabulate(display_df, headers="keys", tablefmt="pretty", showindex=False))
        
        return total_count, len(response.data)
    
    except Exception as e:
        print(f"Error viewing emails by category '{category}': {e}")
        return 0, 0

def view_email_detail(email_id):
    """View detailed information for a specific email"""
    try:
        response = supabase.table("emails").select("*").eq("id", email_id).single().execute()
        
        if not response.data:
            print(f"No email found with ID {email_id}")
            return
        
        email = response.data
        
        print(f"\n=== Email Details for ID {email_id} ===\n")
        print(f"Subject: {email.get('subject', '')}")
        print(f"From: {email.get('sender', '')}")
        print(f"To: {email.get('recipient', '')}")
        
        if 'cc' in email and email['cc']:
            print(f"CC: {email['cc']}")
        
        if 'bcc' in email and email['bcc']:
            print(f"BCC: {email['bcc']}")
        
        print(f"Date: {format_date(email.get('received_date', ''))}")
        print(f"Category: {email.get('category', '')}")
        print(f"Processing Status: {email.get('processing_status', '')}")
        
        print("\n--- Email Body ---\n")
        print(email.get('body', ''))
        
    except Exception as e:
        print(f"Error viewing email detail for ID {email_id}: {e}")

def count_emails_by_category():
    """Count emails in each category"""
    try:
        categories = ["respond", "notify", "done", "ignore"]
        counts = {}
        
        print("\n=== Email Counts by Category ===\n")
        
        for category in categories:
            count_response = supabase.table("emails").select(
                "id", count="exact"
            ).eq("category", category).execute()
            count = count_response.count
            counts[category] = count
            print(f"- {category.capitalize()}: {count}")
        
        # Count for all emails
        all_count_response = supabase.table("emails").select(
            "id", count="exact"
        ).execute()
        all_count = all_count_response.count
        
        print(f"- Total: {all_count}")
        
    except Exception as e:
        print(f"Error counting emails by category: {e}")

def main():
    parser = argparse.ArgumentParser(description='View Supabase database contents')
    
    # Define commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List tables command
    list_parser = subparsers.add_parser('list', help='List all tables')
    
    # View table command
    view_parser = subparsers.add_parser('view', help='View contents of a table')
    view_parser.add_argument('table', help='Table name to view')
    view_parser.add_argument('--limit', type=int, default=10, help='Number of rows to display')
    view_parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    view_parser.add_argument('--where', help='Filter condition (e.g., "category=respond")')
    view_parser.add_argument('--order', help='Order by field (e.g., "received_date:desc")')
    
    # View emails by category command
    category_parser = subparsers.add_parser('category', help='View emails by category')
    category_parser.add_argument('name', help='Category name (respond, notify, done, ignore)')
    category_parser.add_argument('--limit', type=int, default=10, help='Number of rows to display')
    category_parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    
    # View email detail command
    detail_parser = subparsers.add_parser('detail', help='View email detail')
    detail_parser.add_argument('id', type=int, help='Email ID to view')
    
    # Count emails by category command
    count_parser = subparsers.add_parser('count', help='Count emails by category')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute command
    if args.command == 'list':
        list_tables()
    elif args.command == 'view':
        total, displayed = view_table(args.table, args.limit, args.offset, args.where, args.order)
        if total > displayed:
            print(f"\nShowing {displayed} of {total} rows. Use --offset to see more.")
    elif args.command == 'category':
        total, displayed = view_emails_by_category(args.name, args.limit, args.offset)
        if total > displayed:
            print(f"\nShowing {displayed} of {total} rows. Use --offset to see more.")
    elif args.command == 'detail':
        view_email_detail(args.id)
    elif args.command == 'count':
        count_emails_by_category()
    else:
        # Default behavior if no command provided
        parser.print_help()
        print("\n")  # Add a blank line
        list_tables()  # List tables by default

if __name__ == "__main__":
    main()
