#!/usr/bin/env python3
"""
Integration module for the Email Assistant Agent with the Streamlit interface.
This allows the Streamlit app to display agent analysis results when viewing emails.
"""

import os
import sys
import json
from typing import Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the email assistant agent functions
try:
    from email_assistant_agent import (
        get_email_by_id,
        analyze_email_context,
        mark_email_processed,
        format_analysis_for_display
    )
except ImportError:
    # Define fallback functions if agent module not available
    def get_email_by_id(email_id):
        """Fallback function to get an email by ID"""
        return None
        
    def analyze_email_context(email, detailed=True):
        """Fallback function for email analysis"""
        return {"error": "Email Assistant Agent module not available"}
        
    def mark_email_processed(email_id, analysis):
        """Fallback function to mark email as processed"""
        return False
        
    def format_analysis_for_display(analysis):
        """Fallback function to format analysis results"""
        return "Email Assistant Agent module not available"

# Load environment variables
load_dotenv()

# Get Supabase credentials
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

# Initialize Supabase client if credentials available
supabase = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)

class AgentIntegration:
    """Integration class for the Email Assistant Agent"""
    
    def __init__(self):
        """Initialize the agent integration"""
        self.supabase = supabase
    
    def get_agent_analysis(self, email_id: int) -> Optional[Dict[str, Any]]:
        """
        Get agent analysis for an email
        
        Args:
            email_id: ID of the email
            
        Returns:
            Analysis data or None if not available
        """
        if not self.supabase:
            return None
            
        try:
            # First check if the email has been processed by the agent
            response = self.supabase.table("emails").select(
                "processed_by_agent, agent_analysis"
            ).eq("id", email_id).single().execute()
            
            if not response.data:
                return None
                
            # If processed, return the analysis
            if response.data.get("processed_by_agent") and response.data.get("agent_analysis"):
                try:
                    # Convert from string to dict if necessary
                    if isinstance(response.data["agent_analysis"], str):
                        return json.loads(response.data["agent_analysis"])
                    else:
                        return response.data["agent_analysis"]
                except Exception as e:
                    print(f"Error parsing agent analysis: {e}")
                    return None
            
            return None
            
        except Exception as e:
            print(f"Error getting agent analysis: {e}")
            return None
    
    def analyze_email(self, email_id: int) -> Dict[str, Any]:
        """
        Analyze an email using the assistant agent
        
        Args:
            email_id: ID of the email to analyze
            
        Returns:
            Analysis results
        """
        # First try to get existing analysis
        existing = self.get_agent_analysis(email_id)
        if existing:
            return existing
            
        # If no existing analysis, get the email and analyze it
        email = get_email_by_id(email_id)
        if not email:
            return {"error": f"Email with ID {email_id} not found"}
            
        # Perform analysis
        analysis = analyze_email_context(email)
        
        # Mark as processed
        mark_email_processed(email_id, analysis)
        
        return analysis
    
    def format_analysis_for_streamlit(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format analysis results for Streamlit display
        
        Args:
            analysis: Analysis results dictionary
            
        Returns:
            Formatted analysis for Streamlit
        """
        # Check if analysis contains an error
        if "error" in analysis:
            return {
                "success": False,
                "error": analysis["error"],
                "sections": []
            }
            
        # Format analysis into sections for Streamlit display
        sections = []
        
        # Summary section
        if "summary" in analysis and analysis["summary"]:
            sections.append({
                "title": "Summary",
                "content": analysis["summary"],
                "type": "text"
            })
            
        # Key points section
        if "key_points" in analysis and analysis["key_points"]:
            sections.append({
                "title": "Key Points",
                "content": analysis["key_points"],
                "type": "list"
            })
            
        # Inconsistencies section
        if "inconsistencies" in analysis and analysis["inconsistencies"]:
            sections.append({
                "title": "Important Details",
                "content": analysis["inconsistencies"],
                "type": "list"
            })
            
        # Dollar amounts section
        if "dollar_amounts" in analysis and analysis["dollar_amounts"]:
            formatted_amounts = [f"${amount:.2f}" for amount in analysis["dollar_amounts"]]
            sections.append({
                "title": "Dollar Amounts Mentioned",
                "content": formatted_amounts,
                "type": "list"
            })
            
        # Payment references section
        if "payment_references" in analysis and analysis["payment_references"]:
            payment_items = []
            for ref in analysis["payment_references"]:
                amounts = ref.get("amounts", [])
                amount_str = ", ".join([f"${amount:.2f}" for amount in amounts])
                payment_items.append(f"{ref.get('date')} - {ref.get('subject')} - Amounts: {amount_str}")
                
            sections.append({
                "title": "Related Payment References",
                "content": payment_items,
                "type": "list"
            })
            
        # Case references section
        if "case_references" in analysis and analysis["case_references"]:
            sections.append({
                "title": "Case References",
                "content": analysis["case_references"],
                "type": "list"
            })
            
        # Related emails section
        if "related_emails" in analysis and analysis["related_emails"]:
            related_items = []
            for email in analysis["related_emails"]:
                relevance = f" - {email.get('relevance')}" if "relevance" in email else ""
                related_items.append(f"{email.get('date')} - {email.get('subject')}{relevance}")
                
            sections.append({
                "title": "Related Previous Emails",
                "content": related_items,
                "type": "list"
            })
            
        # Suggested responses section
        if "suggested_responses" in analysis and analysis["suggested_responses"]:
            sections.append({
                "title": "Suggested Responses",
                "content": analysis["suggested_responses"],
                "type": "list"
            })
            
        # Questions section
        if "questions" in analysis and analysis["questions"]:
            sections.append({
                "title": "Questions to Consider",
                "content": analysis["questions"],
                "type": "list"
            })
            
        return {
            "success": True,
            "sections": sections
        }
