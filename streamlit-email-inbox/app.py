import streamlit as st
import hmac
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
import pandas as pd
import os
import html2text
from datetime import datetime
from dotenv import load_dotenv
from supabase_utils import (
    get_email_list,
    get_email_detail,
    update_email_category,
    count_emails_by_category,
    get_similar_emails
)
from chatbot_integration import ChatbotIntegration

# Load environment variables
load_dotenv()

# Initialize chatbot
chatbot = ChatbotIntegration()

# HTML to Text converter
html_converter = html2text.HTML2Text()
html_converter.ignore_links = False
html_converter.body_width = 0  # No wrapping

# Set page configuration
st.set_page_config(
    page_title="Law Firm Email Inbox",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Authentication function
def check_password():
    """Returns `True` if the user entered the correct password"""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # Get password from environment or use a default for development
        correct_password = os.environ.get("STREAMLIT_PASSWORD", "lawemail123")
        
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("Law Firm Email Inbox")
    st.subheader("Password Protected")
    st.text_input(
        "Password", type="password", key="password", on_change=password_entered
    )
    if "password_correct" in st.session_state:
        if not st.session_state["password_correct"]:
            st.error("😕 Incorrect password")
    return False

# Initialize session state if needed
if 'selected_email' not in st.session_state:
    st.session_state.selected_email = None
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'email_data' not in st.session_state:
    st.session_state.email_data = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'page_size' not in st.session_state:
    st.session_state.page_size = 10
if 'current_filter' not in st.session_state:
    st.session_state.current_filter = "all"

def format_date(date_string):
    """Format date string to a more readable format"""
    try:
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        # Format: Mar 23, 2025 at 10:30 AM
        return date_obj.strftime("%b %d, %Y at %I:%M %p")
    except Exception as e:
        return date_string

def clean_html_content(html_content):
    """Convert HTML to readable text"""
    if not html_content:
        return ""
    return html_converter.handle(str(html_content))

def get_emails(category=None, page=1, page_size=10):
    """Get emails with pagination and optional category filtering"""
    emails = get_email_list(category, page, page_size)
    if not emails:
        st.error("Error fetching emails")
    return emails

def get_email_details(email_id):
    """Get detailed information for a specific email"""
    email = get_email_detail(email_id)
    if not email:
        st.error("Error fetching email details")
    return email





def render_sidebar():
    """Render the sidebar with email filters"""
    st.sidebar.title("Email Categories")
    
    # Get email counts
    counts = count_emails_by_category()
    
    # Create styled category buttons
    if st.sidebar.button(f"📥 All Emails ({counts.get('all', 0)})", 
                       use_container_width=True,
                       key="all_button",
                       type="primary" if st.session_state.current_filter == "all" else "secondary"):
        st.session_state.current_filter = "all"
        st.session_state.current_page = 1
        st.session_state.selected_email = None
        st.rerun()
        
    if st.sidebar.button(f"⚠️ Active ({counts.get('active', 0)})", 
                       use_container_width=True,
                       key="active_button",
                       type="primary" if st.session_state.current_filter == "active" else "secondary"):
        st.session_state.current_filter = "active"
        st.session_state.current_page = 1
        st.session_state.selected_email = None
        st.rerun()
        
    if st.sidebar.button(f"🔔 Respond ({counts.get('respond', 0)})", 
                       use_container_width=True,
                       key="respond_button",
                       type="primary" if st.session_state.current_filter == "respond" else "secondary"):
        st.session_state.current_filter = "respond"
        st.session_state.current_page = 1
        st.session_state.selected_email = None
        st.rerun()
        
    if st.sidebar.button(f"📢 Notify ({counts.get('notify', 0)})", 
                       use_container_width=True,
                       key="notify_button",
                       type="primary" if st.session_state.current_filter == "notify" else "secondary"):
        st.session_state.current_filter = "notify"
        st.session_state.current_page = 1
        st.session_state.selected_email = None
        st.rerun()
        
    if st.sidebar.button(f"✅ Done ({counts.get('done', 0)})", 
                       use_container_width=True,
                       key="done_button",
                       type="primary" if st.session_state.current_filter == "done" else "secondary"):
        st.session_state.current_filter = "done"
        st.session_state.current_page = 1
        st.session_state.selected_email = None
        st.rerun()
    
    # Page size selector
    st.sidebar.divider()
    st.sidebar.subheader("Settings")
    page_size = st.sidebar.select_slider(
        "Emails per page",
        options=[5, 10, 25, 50],
        value=st.session_state.page_size
    )
    
    if page_size != st.session_state.page_size:
        st.session_state.page_size = page_size
        st.session_state.current_page = 1
        st.rerun()

def render_email_list():
    """Render the email list panel"""
    # Fetch emails based on current filter and pagination
    emails = get_emails(
        category=st.session_state.current_filter,
        page=st.session_state.current_page,
        page_size=st.session_state.page_size
    )
    
    # Title with current filter
    filter_titles = {
        "all": "All Emails",
        "active": "Active Emails",
        "respond": "Emails to Respond",
        "notify": "Notification Emails",
        "done": "Completed Emails"
    }
    st.subheader(filter_titles.get(st.session_state.current_filter, "Emails"))
    
    # Create email list
    for email in emails:
        # Email container with styling
        with st.container(border=True):
            cols = st.columns([4, 1])
            
            # Email info in first column
            with cols[0]:
                # Make the subject clickable
                if st.button(
                    f"**{email['subject']}**", 
                    key=f"email_{email['id']}",
                    use_container_width=True,
                    type="secondary"
                ):
                    st.session_state.selected_email = email['id']
                    st.session_state.chat_messages = []  # Reset chat when selecting new email
                    st.rerun()
                
                # Sender and date
                st.caption(f"From: {email['sender']} • {format_date(email['received_date'])}")
            
            # Category indicator in second column
            with cols[1]:
                category = email.get('category', '').lower()
                if category == 'respond':
                    st.info("Respond", icon="🔔")
                elif category == 'notify':
                    st.success("Notify", icon="📢")
                elif category == 'done':
                    st.info("Done", icon="✅")
                else:
                    st.info(category.capitalize() if category else "Unknown")
    
    # Pagination controls
    st.divider()
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        if st.session_state.current_page > 1:
            if st.button("← Previous", use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()
    
    with col2:
        st.write(f"Page {st.session_state.current_page}")
    
    with col3:
        # We don't know the total number of pages, but we can always show Next
        # If there are no more emails, the Next button will just show empty results
        if len(emails) == st.session_state.page_size:  # If we have a full page, there might be more
            if st.button("Next →", use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()

def render_email_detail():
    """Render the email detail panel"""
    if st.session_state.selected_email:
        # Fetch the full email details
        email_detail = get_email_details(st.session_state.selected_email)
        
        if email_detail:
            # Store email data for chat context
            st.session_state.email_data = email_detail
            
            # Create header with buttons for actions
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.subheader(email_detail['subject'])
            
            # Button to mark as done if not already done
            if email_detail.get('category') != 'done':
                with col2:
                    if st.button("Mark as Done", type="primary", use_container_width=True):
                        if update_email_category(email_detail['id'], 'done'):
                            st.success("Email marked as done")
                            st.session_state.selected_email = None
                            st.rerun()
            
            # Button to go back to email list
            with col3:
                if st.button("Back to List", type="secondary", use_container_width=True):
                    st.session_state.selected_email = None
                    st.rerun()
            
            # Email metadata
            st.write(f"**From:** {email_detail['sender']}")
            st.write(f"**To:** {email_detail['recipient']}")
            st.write(f"**Date:** {format_date(email_detail['received_date'])}")
            st.write(f"**Category:** {email_detail.get('category', '').capitalize()}")
            
            # Email body
            st.divider()
            with st.expander("Email Body", expanded=True):
                # Clean the HTML content
                cleaned_content = clean_html_content(email_detail['body'])
                st.markdown(cleaned_content)
        else:
            st.error("Failed to fetch email details")
    else:
        # No email selected - show placeholder
        st.info("Select an email from the list to view details")

def render_chat_interface():
    """Render the chat interface for the selected email"""
    if st.session_state.selected_email and st.session_state.email_data:
        st.subheader("Chat with Law Firm Assistant")
        
        # Display current chat messages
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            # Add user message to chat history
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get response from chatbot
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    # Get response from the chatbot integration
                    response = chatbot.get_response(
                        query=prompt,
                        email_data=st.session_state.email_data,
                        chat_history=st.session_state.chat_messages[:-1]  # Exclude the latest user message
                    )
                    st.markdown(response)
            
            # Add assistant message to chat history
            st.session_state.chat_messages.append({"role": "assistant", "content": response})
            
        # Generate email response button
        if st.button("Generate Email Response Draft", use_container_width=True):
            with st.spinner("Generating email response..."):
                # Get a draft response for the email
                draft = chatbot.generate_email_response(
                    email_data=st.session_state.email_data
                )
                
                # Create a new message with the draft
                draft_message = {
                    "role": "assistant",
                    "content": f"**DRAFT EMAIL RESPONSE:**\n\n```\n{draft}\n```\n\nYou can modify this draft as needed."
                }
                
                # Add to chat history
                st.session_state.chat_messages.append(draft_message)
                
                # Force rerun to display the new message
                st.rerun()
    else:
        # No email selected - show placeholder
        st.info("Select an email to chat about it")

def main():
    """Main application function"""
    # Check password first
    if not check_password():
        st.stop()  # Stop execution if password is incorrect
    
    # Page layout
    st.title("Law Firm Email Inbox")
    
    # Create a 2-column layout
    col1, col2 = st.columns([3, 7])
    
    # Render the sidebar
    render_sidebar()
    
    # Email list in first column
    with col1:
        render_email_list()
    
    # Email detail and chat in second column
    with col2:
        tabs = st.tabs(["Email", "Chat"])
        
        with tabs[0]:  # Email tab
            render_email_detail()
            
        with tabs[1]:  # Chat tab
            render_chat_interface()

if __name__ == "__main__":
    main()
