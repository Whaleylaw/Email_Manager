#!/usr/bin/env python3
"""
Simplified Email Triage Agent using CrewAI

This module contains the CrewAI Agent implementation for triaging emails
from Gmail before they are added to the Supabase vector store.
"""

import os
import re
from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel
from typing import Literal


class EmailTriageState(BaseModel):
    """
    State model for the email triage flow
    """
    email_subject: str = ""
    email_body: str = ""
    email_sender: str = ""
    triage_category: Literal["ignore", "notify", "respond"] = "notify"  # Default to notify if unsure
    triage_reasoning: str = ""


class EmailTriageAgent:
    """Email triage agent using CrewAI to evaluate email importance"""
    
    def __init__(self, triage_instructions=None):
        """
        Initialize the email triage agent with instructions
        
        Args:
            triage_instructions: Dictionary containing triage instructions for each category
        """
        self.triage_instructions = triage_instructions or {}
        self._load_default_instructions()
        self._create_agent()
        
    def _load_default_instructions(self):
        """Load default triage instructions if none provided"""
        if "triage_no" not in self.triage_instructions:
            self.triage_instructions["triage_no"] = """
                - Automatic platform notifications from social media platforms, online communities, or forums
                - Notification emails from platforms like Medium, Skool, etc. that show "new notifications"
                - Emails with "View Online" links at the top
                - Emails with tracking links and unsubscribe options
                - Marketing emails and newsletters
                - Promotional content from any company or service
                - Emails with "limited time offers" or discounts
                - Mass email announcements
                - "New notification" digests from any platform
                - Subscription newsletters and content updates
                - Emails from noreply@ addresses
                - Any email with multiple tracking links
                - Emails containing the phrases "unsubscribe", "view in browser", "receiving too many emails"
                - Notification summaries ("here's what you missed")
                - Emails from online services unrelated to legal work
            """
            
        if "triage_notify" not in self.triage_instructions:
            self.triage_instructions["triage_notify"] = """
                - Notifications of court filings
                - Emails from Filevine
                - Emails from Blazeo
                - ALL voicemails, texts or faxes from Ring Central
                - ALL bills, invoices, payment notifications, or any financial notifications
                - Any email discussing a legal case
                - Emails about Whaley Law Firm operations or logistics
                - Emails with clear action items from previous conversations
                - Emails about new clients or client questions
                - Updates on ongoing cases
                - Industry news relevant to legal practice
                - Emails from known contacts
                - Receipts or confirmations of services
                - Any email referencing a case name or client name
            """
            
        if "triage_respond" not in self.triage_instructions:
            self.triage_instructions["triage_respond"] = """
                - ALL emails from attorneys
                - ALL emails about specific cases or that mention case names
                - Emails from clients 
                - Emails from Whaley Law Firm team members (Justin@whaleylawfirm.com, Faye@whaleylawfirm.com, Bryce@whaleylawfirm.com, Sarena@whaleylawfirm.com, Jessa@whaleylawfirm.com, Aries@whaleylawfirm.com, or Jessica@whaleylawfirm.com)
                - Emails where it seems Aaron has a pre-existing relationship with the sender
                - Emails mentioning previous meetings or conversations with Aaron
                - Emails from friends
                - Emails that explicitly ask Aaron questions or request information
                - Urgent matters requiring attention
                - Time-sensitive requests or deadlines
                - Messages that specifically ask for Aaron's input or decision
                - Emails containing legal questions 
                - Emails about court cases, hearings, or legal proceedings
            """
    
    def _create_agent(self):
        """Create the CrewAI agent for email triage"""
        # First detect and clean the instructions
        for key in self.triage_instructions:
            # Clean up the instructions by removing excess whitespace
            self.triage_instructions[key] = "\n".join([
                line.strip() for line in self.triage_instructions[key].split("\n")
                if line.strip()
            ])
        
        backstory = f"""
        You are an expert email triage agent for Aaron at Whaley Law Firm.
        Your job is to analyze incoming emails and categorize them into one of three categories.
        
        You should be AGGRESSIVE about filtering out marketing, notification, and promotional emails.
        When in doubt about marketing or notification emails, choose IGNORE rather than notify.
        
        1. IGNORE: Emails to be ignored and not imported.
        Examples of emails to IGNORE:
        {self.triage_instructions.get("triage_no", "")}
        
        2. NOTIFY: Emails that Aaron should be notified about but may not need immediate response.
        Examples of emails to NOTIFY:
        {self.triage_instructions.get("triage_notify", "")}
        
        3. RESPOND: Emails that require Aaron's attention and response.
        Examples of emails to RESPOND:
        {self.triage_instructions.get("triage_respond", "")}
        
        DEFAULT BEHAVIOR RULES:
        1. Be AGGRESSIVE about filtering out marketing and notifications - when in doubt, IGNORE them
        2. For emails from actual people, clients, attorneys or about cases, be cautious - default to NOTIFY
        3. If you see "notification", "digest", "update", or similar terms in the subject - IGNORE
        4. If you see marketing language, promotional offers, or unsubscribe links - IGNORE
        5. Never choose "notify" for obvious platform notifications like "You have new notifications" emails
        
        Your output should begin with EXACTLY ONE of these words on the first line: 
        "ignore", "notify", or "respond" 
        
        Then provide your detailed reasoning on subsequent lines.
        """
        
        self.agent = Agent(
            role="Email Triage Specialist",
            goal="Categorize emails accurately based on importance and need for response",
            backstory=backstory,
            verbose=True
        )
        
        self.task = Task(
            description="""
            Analyze the provided email and categorize it as one of:
            - ignore (emails to be filtered out)
            - notify (emails Aaron should know about)
            - respond (emails requiring response)
            
            Default to IGNORE for marketing, notification digests, and promotional emails.
            Be AGGRESSIVE about filtering out these types of emails.
            Only use notify/respond for emails from real people, clients, or about cases.
            
            Start your response with EXACTLY ONE of these words on the first line: 
            "ignore", "notify", or "respond"
            
            Then provide a detailed explanation of your reasoning.
            """,
            expected_output="A category (ignore, notify, or respond) on the first line, followed by a detailed explanation",
            agent=self.agent
        )
    
    def _analyze_email_indicators(self, subject, body, sender):
        """
        Pre-analyze email for common indicators of importance or clear marketing/notification emails
        
        Returns:
            tuple: (likely_category, confidence, reasoning)
        """
        subject_lower = subject.lower() if subject else ""
        body_lower = body.lower() if body else ""
        sender_lower = sender.lower() if sender else ""
        
        # QUICK PATTERN MATCHING - These are high-confidence cases we can decide immediately
        
        # Check for critical communications that should never be ignored
        
        # 1. Voice/text/fax messages from RingCentral
        if any(term in subject_lower for term in ["voice message", "text message", "fax"]) and "ringcentral" in sender_lower:
            return "notify", 0.95, "Message notification from RingCentral"
            
        # 2. Bills and payments
        if ("bill" in subject_lower and "due" in subject_lower) or "payment required" in subject_lower:
            return "notify", 0.95, "Bill or payment notification"
        
        # 3. Legal communications
        legal_indicators = [
            "case", "court", "filing", "attorney", "lawyer", "legal", 
            "hearing", "plaintiff", "defendant", "estate", "vs.", "v."
        ]
        
        for indicator in legal_indicators:
            if indicator in subject_lower:
                return "respond", 0.95, f"Legal term in subject: '{indicator}'"
        
        # 4. Team member communications
        team_domains = ["whaleylawfirm.com", "filevine.com", "blazeo.com"]
        is_team_member = any(domain in sender_lower for domain in team_domains)
        
        if is_team_member:
            return "respond", 0.95, "Email from team member domain"
        
        # AGGRESSIVE FILTERING OF MARKETING/NOTIFICATION EMAILS
        
        # 1. Platform notifications and digests
        platform_indicators = [
            "new notification" in subject_lower,
            "notification" in subject_lower and not "court" in subject_lower,
            "digest" in subject_lower,
            "what you missed" in body_lower,
            "notification since" in body_lower,
            "noreply" in sender_lower,
            "no-reply" in sender_lower,
            "donotreply" in sender_lower,
            "notification" in sender_lower,
            "updates" in subject_lower and "new" in subject_lower,
            any(domain in sender_lower for domain in ["skool.com", "medium.com", "facebook.com", "twitter.com", "linkedin.com"]),
            "view online" in body_lower[:500],
            "view in browser" in body_lower,
            "email preferences" in body_lower,
            "unsubscribe" in body_lower and ("offer" in body_lower or "discount" in body_lower),
            body_lower.count("http") > 5,  # Many links is a sign of marketing email
            "too many emails" in body_lower
        ]
        
        if any(platform_indicators):
            # Find the first true indicator for better explanation
            for i, indicator in enumerate(platform_indicators):
                if indicator:
                    if i == 0: return "ignore", 0.9, "Email contains 'new notification' in subject"
                    if i == 1: return "ignore", 0.9, "Email contains 'notification' in subject"
                    if i == 2: return "ignore", 0.9, "Email is a digest"
                    if i == 3: return "ignore", 0.9, "Email contains 'what you missed'"
                    if i == 4: return "ignore", 0.9, "Email contains 'notification since'"
                    if i == 5: return "ignore", 0.9, "Email is from noreply address"
                    if i == 6: return "ignore", 0.9, "Email is from no-reply address"
                    if i == 7: return "ignore", 0.9, "Email is from donotreply address"
                    if i == 8: return "ignore", 0.9, "Email is from notification sender"
                    if i == 9: return "ignore", 0.9, "Email contains 'updates' and 'new' in subject"
                    if i == 10: return "ignore", 0.9, "Email is from social/platform domain"
                    if i == 11: return "ignore", 0.9, "Email has 'view online' at top"
                    if i == 12: return "ignore", 0.9, "Email has 'view in browser'"
                    if i == 13: return "ignore", 0.9, "Email mentions email preferences"
                    if i == 14: return "ignore", 0.9, "Email has unsubscribe and offer/discount"
                    if i == 15: return "ignore", 0.9, "Email contains many links (marketing)"
                    if i == 16: return "ignore", 0.9, "Email mentions 'too many emails'"
        
        # 2. Marketing and promotional emails
        marketing_indicators = [
            "offer" in subject_lower,
            "discount" in subject_lower,
            "sale" in subject_lower,
            "deal" in subject_lower,
            "promotion" in subject_lower,
            "special" in subject_lower and "offer" in subject_lower,
            "coupon" in subject_lower,
            "limited time" in subject_lower or "limited time" in body_lower[:500],
            "off" in subject_lower and "%" in subject_lower,
            "exclusive" in subject_lower,
            "reward" in subject_lower and not "law" in subject_lower,
            "pro days" in body_lower[:500],
            "pro days" in subject_lower,
            "come back" in subject_lower, 
            "miss you" in subject_lower,
            "save" in subject_lower and "$" in subject_lower
        ]
        
        if any(marketing_indicators):
            return "ignore", 0.9, "Email contains marketing/promotional content"
            
        # No conclusive indicators found, letting the AI do more detailed analysis
        return None, 0, "No conclusive indicators found, need AI analysis"
        
    def triage_email(self, subject, body, sender):
        """
        Triage an email using the CrewAI agent
        
        Args:
            subject: Email subject
            body: Email body text
            sender: Email sender address
            
        Returns:
            tuple: (category, reasoning)
                category - one of: ignore, notify, respond
                reasoning - explanation for the categorization
        """
        # First do a basic analysis for high-confidence cases
        pre_category, confidence, pre_reasoning = self._analyze_email_indicators(subject, body, sender)
        
        # For high confidence cases, we can skip the AI agent
        if pre_category and confidence >= 0.9:
            return pre_category, f"Automatic categorization: {pre_reasoning}"
            
        # Create a crew with the agent and task
        crew = Crew(
            agents=[self.agent],
            tasks=[self.task],
            verbose=True
        )
        
        # Prepare email content for the agent
        email_content = f"""
        Subject: {subject}
        
        From: {sender}
        
        Body:
        {body}
        """
        
        # Run the crew with the email content
        result = crew.kickoff(inputs={"email": email_content})
        
        # Parse the result - expected format is "category\nreasoning"
        result_text = result.raw.strip()
        
        # Split by newline to separate category from reasoning
        parts = result_text.split("\n", 1)
        if len(parts) >= 1:
            category_text = parts[0].lower().strip()
            reasoning = parts[1].strip() if len(parts) > 1 else "No reasoning provided"
            
            # Extract category - look for exact matches
            if category_text == "ignore":
                category = "ignore"
            elif category_text == "notify":
                category = "notify"
            elif category_text == "respond":
                category = "respond"
            else:
                # If the first line isn't exactly one of our categories, default to notify
                category = "notify"
                reasoning = f"Could not determine exact category from '{category_text}', defaulting to 'notify'.\n{result_text}"
        else:
            # Default if we can't parse the result
            category = "notify"
            reasoning = f"Failed to parse result: {result_text}"
            
        # Apply safeguards to prevent important emails from being ignored
        
        # Voice messages, texts, faxes from RingCentral should never be ignored
        if category == "ignore" and any(term in subject.lower() for term in ["voice message", "text message", "fax"]) and "ringcentral" in sender.lower():
            category = "notify"
            reasoning = f"SAFEGUARD OVERRIDE: Voice/text/fax messages should not be ignored.\nOriginal reasoning: {reasoning}"
            
        # Emails about cases or from attorneys should never be ignored
        legal_terms = ["case", "court", "attorney", "estate", "v.", "vs.", "plaintiff", "defendant"]
        if category == "ignore" and any(term in subject.lower() for term in legal_terms):
            category = "respond"
            reasoning = f"SAFEGUARD OVERRIDE: Legal correspondence should not be ignored.\nOriginal reasoning: {reasoning}"
            
        # Emails about bills should never be ignored
        if category == "ignore" and ("bill" in subject.lower() and "due" in subject.lower()):
            category = "notify"
            reasoning = f"SAFEGUARD OVERRIDE: Bills and payment notices should not be ignored.\nOriginal reasoning: {reasoning}"
                
        return category, reasoning


class EmailTriageFlow(Flow[EmailTriageState]):
    """Flow for triaging an email using CrewAI"""
    
    def __init__(self):
        """Initialize the email triage flow"""
        super().__init__()
        self.triage_agent = EmailTriageAgent()
    
    @start()
    def process_email(self):
        """Process an email and determine its triage category"""
        print(f"Processing email: {self.state.email_subject}")
        
        # Use the triage agent to categorize the email
        category, reasoning = self.triage_agent.triage_email(
            self.state.email_subject,
            self.state.email_body,
            self.state.email_sender
        )
        
        # Update the state with the triage results
        self.state.triage_category = category
        self.state.triage_reasoning = reasoning
        
        print(f"Email categorized as: {category}")
        print(f"Reasoning: {reasoning}")
        
        return category