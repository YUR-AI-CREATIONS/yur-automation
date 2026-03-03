"""
Superagent Modules - All autonomous sales agents
"""

from .prospector import LinkedInProspector
from .emailer import EmailSequencer
from .call_handler import CallHandler

__all__ = [
    "LinkedInProspector",
    "EmailSequencer", 
    "CallHandler",
]
