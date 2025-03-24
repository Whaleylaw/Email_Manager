import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

# Configure Supabase
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def get_email_list(
    category: Optional[str] = None, 
    page: int = 1, 
    page_size: int = 10
) -> List[Dict[str, Any]]:
    """
    Get emails with pagination and optional category filtering
    
    Args:
        category: Optional filter for email category (respond, notify, done, active)
        page: Page number starting at 1
        page_size: Number of emails per page
    
    Returns:
        List of email dictionaries with basic info
    """
    query = supabase.table("emails").select(
        "id, subject, sender, recipient, received_date, category"
    ).order("received_date", desc=True)
    
    # Apply category filter if specified
    if category == "respond":
        query = query.eq("category", "respond")
    elif category == "notify":
        query = query.eq("category", "notify")
    elif category == "done":
        query = query.eq("category", "done")
    elif category == "active":
        # Active emails are those that need attention (respond or notify)
        query = query.in_("category", ["respond", "notify"])
    
    # Calculate pagination
    start = (page - 1) * page_size
    end = start + page_size - 1
    
    # Apply pagination
    query = query.range(start, end)
    
    try:
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Error fetching emails: {e}")
        return []

def get_email_detail(email_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed information for a specific email
    
    Args:
        email_id: ID of the email to retrieve
    
    Returns:
        Email dictionary with full details or None if not found
    """
    try:
        response = supabase.table("emails").select("*").eq("id", email_id).single().execute()
        return response.data
    except Exception as e:
        print(f"Error fetching email details: {e}")
        return None

def update_email_category(email_id: int, category: str) -> bool:
    """
    Update the category of an email
    
    Args:
        email_id: ID of the email to update
        category: New category (respond, notify, done)
    
    Returns:
        Boolean indicating success
    """
    try:
        response = supabase.table("emails").update(
            {"category": category}
        ).eq("id", email_id).execute()
        return True
    except Exception as e:
        print(f"Error updating email category: {e}")
        return False

def count_emails_by_category() -> Dict[str, int]:
    """
    Count emails in each category
    
    Returns:
        Dictionary with counts for each category
    """
    try:
        # Try using a custom RPC function if available
        try:
            response = supabase.rpc(
                "count_emails_by_category"
            ).execute()
            
            # Process the RPC response if it exists
            if response.data:
                result = {}
                for item in response.data:
                    result[item["category"]] = item["count"]
                    
                # Calculate additional counts
                result["all"] = sum(result.values())
                result["active"] = result.get("respond", 0) + result.get("notify", 0)
                return result
        except:
            pass
        
        # Fallback to multiple queries if RPC doesn't exist
        categories = ["respond", "notify", "done"]
        counts = {}
        
        for category in categories:
            count_response = supabase.table("emails").select(
                "id", count="exact"
            ).eq("category", category).execute()
            counts[category] = count_response.count
            
        # Count for all emails
        all_count_response = supabase.table("emails").select(
            "id", count="exact"
        ).execute()
        counts["all"] = all_count_response.count
        
        # Count for active emails (respond or notify)
        active_count_response = supabase.table("emails").select(
            "id", count="exact"
        ).in_("category", ["respond", "notify"]).execute()
        counts["active"] = active_count_response.count
        
        return counts
            
    except Exception as e:
        print(f"Error counting emails: {e}")
        return {"all": 0, "respond": 0, "notify": 0, "done": 0, "active": 0}

def get_similar_emails(email_id: int, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Find emails similar to the given email using vector search
    
    Args:
        email_id: ID of the reference email
        limit: Maximum number of similar emails to return
    
    Returns:
        List of similar email dictionaries
    """
    try:
        # First get the embedding of the target email
        email_data = get_email_detail(email_id)
        if not email_data:
            return []
            
        # Try to find similar emails using vector search if available
        try:
            similar_response = supabase.rpc(
                "find_similar_emails",
                {"reference_email_id": email_id, "match_count": limit}
            ).execute()
            
            if similar_response.data:
                return similar_response.data
        except:
            # Fallback to returning recent emails if vector search not available
            recent_response = supabase.table("emails").select(
                "id, subject, sender, received_date, category"
            ).neq("id", email_id).order("received_date", desc=True).limit(limit).execute()
            
            return recent_response.data
            
    except Exception as e:
        print(f"Error finding similar emails: {e}")
        return []
