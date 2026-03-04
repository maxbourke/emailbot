#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pyyaml>=6.0",
#   "requests>=2.31.0",
# ]
# ///
"""
EmailBot - A minimal email automation tool.

Reads contacts, rules, company context, and campaign description to generate
and optionally send personalized emails via OpenRouter AI and Gmail SMTP.
"""

import argparse
import csv
import datetime
import os
import smtplib
import ssl
import time
import textwrap
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Tuple
import json

import yaml
import requests


def load_contacts(path: str) -> List[Dict]:
    """Load contacts from CSV file."""
    contacts = []
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            contacts.append(dict(row))
    return contacts


def load_rules(path: str) -> Dict:
    """Load rules configuration from YAML file."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_company(path: str) -> Dict:
    """Load company configuration from YAML file."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_campaign(path: str) -> str:
    """Load campaign description from text file."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def load_signature(path: str = "signatures/default.txt") -> str:
    """Load email signature from text file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""  # Return empty signature if file not found


def should_email(contact: Dict, rules: Dict, today: datetime.date) -> Tuple[bool, str]:
    """
    Determine if a contact should be emailed based on rules and last contact date.
    Returns (should_email, reason).
    """
    contact_type = contact['contact_type']
    last_contacted_str = contact['last_contacted']
    
    if contact_type not in rules['rules']:
        return False, f"No rules defined for contact type: {contact_type}"
    
    min_days = rules['rules'][contact_type]['min_days_between_emails']
    
    try:
        last_contacted = datetime.datetime.fromisoformat(last_contacted_str).date()
    except ValueError:
        return False, f"Invalid date format: {last_contacted_str}"
    
    days_since_contact = (today - last_contacted).days
    
    if days_since_contact < min_days:
        return False, f"contacted {days_since_contact} days ago, min {min_days} days"
    
    return True, f"last contacted {days_since_contact} days ago (min {min_days})"


def generate_email_body(openrouter_config: Dict, company_config: Dict, 
                       campaign_text: str, contact: Dict) -> Tuple[str, str]:
    """
    Generate personalized email subject and body using OpenRouter API.
    Returns (subject, body).
    """
    api_key_env = openrouter_config['api_key_env']
    api_key = os.environ.get(api_key_env)
    
    if not api_key:
        raise ValueError(f"API key not found in environment variable: {api_key_env}")
    
    # Build the system message
    system_message = f"""You are writing short, personalized, non-spammy emails for {company_config['company_name']}.

Brand voice: {company_config['brand_voice']}

Guidelines:
- Keep emails to 2-4 paragraphs maximum
- Be friendly and professional but concise
- Avoid over-promising or excessive sales language
- Respect the recipient's time
- Don't sound like spam or templated
- Use proper Australian English spelling and tone
- Don't include placeholder text like [Your Name], [Phone], [Email] - the signature will be added separately
- Keep paragraphs short and readable
- End with a simple, friendly sign-off

CRITICAL: Respond in this exact format with no extra text:
Subject: [your subject line]

[email body content ending with a simple sign-off like "Cheers," or "Best regards,"]"""

    # Build the user message with campaign and contact details
    today = datetime.date.today()
    user_message = f"""Campaign Description:
{campaign_text}

Contact Details:
- Name: {contact['first_name']} {contact['last_name']}
- Contact Type: {contact['contact_type']}
- Details: {contact['details']}
- Email: {contact['email']}

Context:
- Today's date: {today.strftime('%B %d, %Y')}
- For existing customers: Consider how long they've owned their current pool when deciding whether to mention upgrades

Please write a personalized email for this contact based on the campaign description and their contact type."""

    # Make API request to OpenRouter with retry logic
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': openrouter_config['model'],
        'messages': [
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': user_message}
        ]
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                openrouter_config['base_url'],
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                break
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10  # 10, 20, 30 seconds
                    print(f"  Rate limited, waiting {wait_time} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"OpenRouter API rate limited after {max_retries} attempts")
            else:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"  Request failed, retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                raise Exception(f"Request failed after {max_retries} attempts: {e}")
    
    result = response.json()
    content = result['choices'][0]['message']['content']
    
    return parse_openrouter_response(content)


def parse_openrouter_response(content: str) -> Tuple[str, str]:
    """
    Parse OpenRouter response to extract subject and body.
    Returns (subject, body).
    """
    lines = content.strip().split('\n')
    
    subject = ""
    body_lines = []
    found_subject = False
    
    for line in lines:
        if line.startswith('Subject:') and not found_subject:
            subject = line[8:].strip()
            found_subject = True
        elif found_subject and line.strip() == "":
            # Skip empty lines after subject
            continue
        elif found_subject:
            body_lines.append(line)
    
    body = '\n'.join(body_lines).strip()
    
    if not subject:
        subject = "Update from [Company]"
    
    return subject, body


def send_or_preview_email(contact: Dict, subject: str, body: str, 
                         company_config: Dict, is_dry_run: bool, run_timestamp: str = None, 
                         signature: str = "") -> None:
    """
    Either send the email via Gmail SMTP or preview it.
    """
    recipient = contact['email']
    from_name = company_config['default_from_name']
    from_email = company_config['default_from_email']
    reply_to = company_config['default_reply_to']
    
    # Add signature to body if provided
    if signature:
        body = f"{body}\n\n{signature}"
    
    if is_dry_run:
        # Print preview
        print(f"\n{'='*60}")
        print(f"PREVIEW EMAIL")
        print(f"{'='*60}")
        print(f"To: {contact['first_name']} {contact['last_name']} <{recipient}>")
        print(f"From: {from_name} <{from_email}>")
        print(f"Reply-To: {reply_to}")
        print(f"Subject: {subject}")
        print(f"")
        print(textwrap.fill(body, width=70))
        print(f"{'='*60}")
        
        # Also save to .eml file in Test_Outputs directory with timestamp
        if run_timestamp is None:
            run_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = f"Test_Outputs/dry_run_{run_timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        email_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # microseconds to milliseconds
        email_filename = f"{output_dir}/{contact['email'].replace('@', '_at_')}_{email_timestamp}.eml"
        
        eml_content = f"""To: {contact['first_name']} {contact['last_name']} <{recipient}>
From: {from_name} <{from_email}>
Reply-To: {reply_to}
Subject: {subject}

{body}
"""
        
        with open(email_filename, 'w', encoding='utf-8') as f:
            f.write(eml_content)
        
        print(f"Saved to: {email_filename}")
        
    else:
        # Send via Gmail SMTP
        print(f"Sending to {contact['first_name']} {contact['last_name']} <{recipient}>...")
        
        try:
            # Get SMTP configuration
            smtp_config = company_config.get('smtp', {})
            if not smtp_config:
                raise Exception("No SMTP configuration found in company.yaml")
            
            # Get credentials from environment
            gmail_username = os.environ.get(smtp_config['username_env'])
            gmail_password = os.environ.get(smtp_config['password_env'])
            
            if not gmail_username or not gmail_password:
                raise Exception(f"Gmail credentials not found. Set {smtp_config['username_env']} and {smtp_config['password_env']} environment variables")
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{from_name} <{gmail_username}>"
            msg['To'] = recipient
            msg['Subject'] = subject
            msg['Reply-To'] = reply_to
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Send via SMTP
            print(f"  Connecting to {smtp_config['host']}:{smtp_config['port']}")
            
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
                if smtp_config.get('use_tls', True):
                    server.starttls(context=context)
                server.login(gmail_username, gmail_password)
                
                text = msg.as_string()
                server.sendmail(gmail_username, recipient, text)
            
            print(f"✓ Email sent successfully to {recipient}")
                
        except Exception as e:
            print(f"✗ Error sending email to {recipient}: {e}")
        
        # Delay between sends
        time.sleep(5)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="EmailBot - Automated email campaigns with AI-generated content"
    )
    parser.add_argument('--contacts', required=True, help='Path to contacts CSV file')
    parser.add_argument('--rules', required=True, help='Path to rules YAML file')
    parser.add_argument('--company', required=True, help='Path to company YAML file')
    parser.add_argument('--campaign', required=True, help='Path to campaign text file')
    parser.add_argument('--send', action='store_true', help='Actually send emails (default: dry run)')
    parser.add_argument('--dry-run', action='store_true', help='Preview emails only (default)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt when sending')
    
    args = parser.parse_args()
    
    # Default to dry run if neither --send nor --dry-run specified
    if not args.send and not args.dry_run:
        args.dry_run = True
    
    # Load all configuration files
    print("Loading configuration...")
    contacts = load_contacts(args.contacts)
    rules = load_rules(args.rules)
    company_config = load_company(args.company)
    campaign_text = load_campaign(args.campaign)
    signature = load_signature()
    
    print(f"Loaded {len(contacts)} contacts")
    
    # Filter contacts based on rules
    today = datetime.date.today()
    contacts_to_email = []
    
    print(f"\nFiltering contacts (today: {today})...")
    for contact in contacts:
        should_send, reason = should_email(contact, rules, today)
        
        if should_send:
            contacts_to_email.append(contact)
            print(f"✓ {contact['first_name']} {contact['last_name']} ({contact['contact_type']}): {reason}")
        else:
            print(f"✗ Skipped {contact['first_name']} {contact['last_name']} ({contact['contact_type']}): {reason}")
    
    if not contacts_to_email:
        print("\nNo contacts to email based on current rules.")
        return
    
    print(f"\nWill email {len(contacts_to_email)} contacts")
    
    if args.send:
        print("REAL SENDING MODE - emails will be sent via Gmail SMTP")
        if args.yes:
            print("Skipping confirmation due to --yes flag")
            confirm = 'y'
        else:
            confirm = input("Are you sure? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                return
    else:
        print("DRY RUN MODE - emails will be previewed only")
    
    # Generate and send/preview emails
    openrouter_config = rules['openrouter']
    run_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for i, contact in enumerate(contacts_to_email, 1):
        print(f"\n[{i}/{len(contacts_to_email)}] Processing {contact['first_name']} {contact['last_name']}...")
        
        try:
            subject, body = generate_email_body(openrouter_config, company_config, campaign_text, contact)
            send_or_preview_email(contact, subject, body, company_config, args.dry_run, run_timestamp, signature)
            
        except Exception as e:
            print(f"✗ Error processing {contact['email']}: {e}")
            continue
    
    print(f"\nCompleted processing {len(contacts_to_email)} contacts")


if __name__ == "__main__":
    main()