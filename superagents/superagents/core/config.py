"""
Superagent Configuration
Load from environment variables with sensible defaults
"""

import os
from typing import Optional


class SuperagentConfig:
    """Central configuration for all superagents"""
    
    # Trinity Backend
    TRINITY_API_URL = os.getenv("TRINITY_API_URL", "https://yur-ai-api.onrender.com")
    TRINITY_API_KEY = os.getenv("TRINITY_API_KEY", "")
    
    # OpenAI (for intelligent responses)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # LinkedIn API (for prospecting + engagement)
    LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    LINKEDIN_ORG_ID = os.getenv("LINKEDIN_ORG_ID", "")
    
    # Email (Gmail/Sendgrid)
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "gmail")  # gmail or sendgrid
    GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
    GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")
    
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "sales@yourcompany.com")
    FROM_NAME = os.getenv("FROM_NAME", "Trinity Sales")
    RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")  # For testing/demo emails
    
    # Calendar (Calendly)
    CALENDLY_TOKEN = os.getenv("CALENDLY_TOKEN", "")
    CALENDLY_USERNAME = os.getenv("CALENDLY_USERNAME", "")
    
    # Video Recording (Gong/Video API)
    GONG_ACCESS_KEY = os.getenv("GONG_ACCESS_KEY", "")
    GONG_REFRESH_TOKEN = os.getenv("GONG_REFRESH_TOKEN", "")
    
    # Transcription (Otter.ai or Assembly.ai)
    TRANSCRIPTION_SERVICE = os.getenv("TRANSCRIPTION_SERVICE", "otter")  # otter or assembly
    OTTER_API_KEY = os.getenv("OTTER_API_KEY", "")
    ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY", "")
    
    # CRM Integration (HubSpot)
    HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY", "")
    HUBSPOT_PORTAL_ID = os.getenv("HUBSPOT_PORTAL_ID", "")
    
    # Crunchbase (for company research)
    CRUNCHBASE_API_KEY = os.getenv("CRUNCHBASE_API_KEY", "")
    
    # Phone/Telephony (Twilio)
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # Slack (for notifications)
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL_SALES = os.getenv("SLACK_CHANNEL_SALES", "#sales")
    SLACK_CHANNEL_ALERTS = os.getenv("SLACK_CHANNEL_ALERTS", "#alerts")
    
    # Database (for local caching)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///superagents.db")
    
    # Agent Configuration
    DAILY_MAX_EMAILS = int(os.getenv("DAILY_MAX_EMAILS", "100"))
    DAILY_MAX_CALLS = int(os.getenv("DAILY_MAX_CALLS", "50"))
    DAILY_MAX_PROPOSALS = int(os.getenv("DAILY_MAX_PROPOSALS", "20"))
    
    # Email Template settings
    EMAIL_TEMPLATE_OPEN_TRACKING = os.getenv("EMAIL_TEMPLATE_OPEN_TRACKING", "true").lower() == "true"
    EMAIL_TEMPLATE_CLICK_TRACKING = os.getenv("EMAIL_TEMPLATE_CLICK_TRACKING", "true").lower() == "true"
    
    # LinkedIn settings
    LINKEDIN_POST_FREQUENCY = os.getenv("LINKEDIN_POST_FREQUENCY", "daily")  # daily, weekly, or none
    LINKEDIN_AUTO_ENGAGEMENT = os.getenv("LINKEDIN_AUTO_ENGAGEMENT", "true").lower() == "true"
    
    # Call handler settings
    CALL_HANDLER_ENABLED = os.getenv("CALL_HANDLER_ENABLED", "true").lower() == "true"
    CALL_HANDLER_GREETING = os.getenv("CALL_HANDLER_GREETING", "Hi! Thanks for calling Trinity Sales. How can I help you today?")
    CALL_HANDLER_TRANSFER_PROMPT = os.getenv("CALL_HANDLER_TRANSFER_PROMPT", "Let me connect you with Jeremy, one of our co-founders.")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "superagents.log")
    
    # Your sales metrics (for personalization)
    YOUR_NAME = os.getenv("YOUR_NAME", "Jeremy")
    YOUR_TITLE = os.getenv("YOUR_TITLE", "Co-Founder & CEO")
    YOUR_PHONE = os.getenv("YOUR_PHONE", "")
    COMPANY_NAME = os.getenv("COMPANY_NAME", "YUR-AI")
    COMPANY_WEBSITE = os.getenv("COMPANY_WEBSITE", "https://yur-ai.com")
    
    # Product info
    PRODUCT_NAME = os.getenv("PRODUCT_NAME", "Trinity Spine")
    PRODUCT_DESCRIPTION = os.getenv("PRODUCT_DESCRIPTION", "Autonomous decision-making engine with governance + quantum crypto + self-healing")
    PRODUCT_PRICE = float(os.getenv("PRODUCT_PRICE", "50000"))  # Annual
    PRODUCT_DEMO_URL = os.getenv("PRODUCT_DEMO_URL", "https://demo.yur-ai.com")
    
    @classmethod
    def validate_required(cls) -> bool:
        """Check if critical config is set"""
        required = [
            "TRINITY_API_URL",
            "OPENAI_API_KEY",
            "FROM_EMAIL",
            "HUBSPOT_API_KEY",
        ]
        missing = [key for key in required if not getattr(cls, key)]
        
        if missing:
            print(f"⚠️  Missing required config: {', '.join(missing)}")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current config (redact secrets)"""
        config_vars = {
            k: v for k, v in cls.__dict__.items()
            if not k.startswith('_') and k.isupper()
        }
        
        for key, value in sorted(config_vars.items()):
            # Redact sensitive values
            if any(secret in key.upper() for secret in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']):
                display_value = f"{str(value)[:10]}***" if value else "[not set]"
            else:
                display_value = value
            
            print(f"{key:30s} = {display_value}")
