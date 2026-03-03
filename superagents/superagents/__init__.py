"""
Superagent Sales Framework
Connected to Trinity Render Backend: https://yur-ai-api.onrender.com/

8 autonomous agents handling full sales pipeline:
1. LinkedIn Prospector - finds 50 leads/day
2. Email Sequencer - 5-email follow-up campaigns
3. Calendar Assistant - schedules meetings automatically
4. Proposal Generator - creates custom proposals in 1 hour
5. Call Transcriber - records + parses calls + updates CRM
6. LinkedIn Engagement Bot - daily posts + engagement + DMs
7. Call Handler - takes exploratory calls, qualifies prospects
8. Objection Handler - closes 5-10% of deals automatically

All agents route through Trinity API for data persistence + governance.
"""

__version__ = "1.0.0"
__author__ = "YUR-AI Trinity Sales Team"

from .core.trinity_client import TrinityClient
from .core.config import SuperagentConfig

# Initialize Trinity client
trinity = TrinityClient(base_url="https://yur-ai-api.onrender.com")
