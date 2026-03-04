"""
Fleet integrations — Bid portals, Procore, OneDrive, LLM.
"""

from .llm import LLMService, llm_completion
from .bid_portals import BidPortalAdapter, SamGovAdapter, BidOpportunity
from .procore_invoices import ProcoreInvoiceBridge
from .onedrive_docs import OneDriveDocBridge

__all__ = [
    "LLMService",
    "llm_completion",
    "BidPortalAdapter",
    "SamGovAdapter",
    "BidOpportunity",
    "ProcoreInvoiceBridge",
    "OneDriveDocBridge",
]
