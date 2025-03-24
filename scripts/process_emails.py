#!/usr/bin/env python3
import os
import time
import sys
from dotenv import load_dotenv
import openai
from supabase import create_client, Client

# Add the parent directory to the path to import from libs
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Configuration
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
openai_api_key = os.environ.get("OPENAI_API_KEY")

if not supabase_url or not supabase_key:
    print("Error: Supabase credentials not found in environment variables")
    sys.exit(1)

if not openai_api_key:
    print("Error: OpenAI API key not found in environment variables")
    sys.exit(1)

# Initialize clients
supabase: Client = create_client(supabase_url, supabase_key)
openai.api_key = openai_api_key

def split_into_chunks(text, chunk_size=2000):
    """Split text into chunks by words."""
    if not text:
        return [""]  # Return a single empty chunk if text is empty
    
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        # +1 for the space
        if current_length + len(word) + 1 > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def process_pending_emails():
    """Process emails marked as pending."""
    try:
        # Get emails with pending status
        response = supabase.table("emails").select("*").eq("processing_status", "pending").execute()
        
        if not response.data:
            print("No pending emails to process")
            return
        
        print(f"Found {len(response.data)} pending emails to process")
        
        for email in response.data:
            email_id = email["id"]
            subject = email.get("subject", "(No Subject)")
            body = email.get("body", "")
            
            print(f"Processing email {email_id}: {subject[:50]}...")
            
            try:
                # Mark as processing
                supabase.table("emails").update({"processing_status": "processing"}).eq("id", email_id).execute()
                
                # Split into chunks
                chunks = split_into_chunks(body)
                print(f"Split into {len(chunks)} chunks")
                
                # Process each chunk
                for i, chunk in enumerate(chunks):
                    # Generate embedding
                    try:
                        embedding_response = openai.embeddings.create(
                            model="text-embedding-3-small",
                            input=chunk
                        )
                        
                        embedding = embedding_response.data[0].embedding
                        
                        # Store in email_sections
                        supabase.table("email_sections").insert({
                            "email_id": email_id,
                            "section_content": chunk,
                            "embedding": embedding,
                            "section_order": i + 1
                        }).execute()
                        
                        print(f"Processed chunk {i+1}/{len(chunks)}")
                    except Exception as chunk_error:
                        print(f"Error processing chunk {i+1}: {chunk_error}")
                
                # Mark as completed
                supabase.table("emails").update({"processing_status": "completed"}).eq("id", email_id).execute()
                print(f"Email {email_id} processed successfully")
                
            except Exception as e:
                print(f"Error processing email {email_id}: {e}")
                # Mark as failed
                supabase.table("emails").update({"processing_status": "failed"}).eq("id", email_id).execute()
    
    except Exception as e:
        print(f"Error in process_pending_emails: {e}")

def run_processing_loop(interval=60):
    """Run the processing loop at regular intervals."""
    print(f"Starting email processing loop (interval: {interval}s)")
    
    while True:
        try:
            process_pending_emails()
        except Exception as e:
            print(f"Error in processing loop: {e}")
        
        time.sleep(interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process pending emails in Supabase')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=60, help='Interval in seconds between runs (default: 60)')
    
    args = parser.parse_args()
    
    if args.once:
        process_pending_emails()
    else:
        run_processing_loop(interval=args.interval)