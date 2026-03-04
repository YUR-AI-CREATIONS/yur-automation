"""
Bid Portal Adapters — Public procurement APIs (SAM.gov, etc.).

SAM.gov: https://open.gsa.gov/api/get-opportunities-public-api/
Requires API key from SAM.gov account. NAICS codes for construction.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BidOpportunity:
    """Parsed bid opportunity."""

    bid_id: str
    title: str
    posted_date: Optional[str]
    due_date: Optional[str]
    agency: Optional[str]
    naics: Optional[str]
    portal: str
    url: Optional[str]
    raw: dict[str, Any]


class BidPortalAdapter(ABC):
    """Abstract adapter for bid portals."""

    @abstractmethod
    def search(
        self,
        *,
        posted_from: Optional[str] = None,
        posted_to: Optional[str] = None,
        naics: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 50,
    ) -> list[BidOpportunity]:
        pass


class SamGovAdapter(BidPortalAdapter):
    """
    SAM.gov Get Opportunities API.

    Env: SAM_GOV_API_KEY (required)
    """
    BASE_URL = "https://api.sam.gov/opportunities/v2/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("SAM_GOV_API_KEY", "")).strip() or None

    def search(
        self,
        *,
        posted_from: Optional[str] = None,
        posted_to: Optional[str] = None,
        naics: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 50,
    ) -> list[BidOpportunity]:
        if not self.api_key:
            logger.warning("SAM_GOV_API_KEY not set; returning empty")
            return []

        today = datetime.now(timezone.utc).date()
        posted_from = posted_from or (today - timedelta(days=7)).isoformat()
        posted_to = posted_to or today.isoformat()

        try:
            import requests
            params = {
                "api_key": self.api_key,
                "postedFrom": posted_from,
                "postedTo": posted_to,
                "limit": min(limit, 100),
            }
            if naics:
                params["naics"] = naics
            if state:
                params["state"] = state

            resp = requests.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            opportunities = []
            raw_list = data.get("opportunitiesData", data.get("opportunities", []))
            for item in raw_list[:limit]:
                opp = item if isinstance(item, dict) else (item.get("opportunity", {}) if isinstance(item, dict) else {})
                if not isinstance(opp, dict):
                    continue
                bid_id = opp.get("noticeId") or opp.get("opportunityId") or opp.get("sol") or opp.get("solicitationNumber") or ""
                title = opp.get("title") or opp.get("sol") or opp.get("solicitationNumber") or ""
                posted = opp.get("postedDate") or opp.get("publishDate")
                due = opp.get("responseDeadLine") or opp.get("closeDate")
                agency = opp.get("fullParentPathName") or opp.get("organization") or opp.get("agency")
                naics_val = opp.get("naicsCode")
                if not naics_val and opp.get("naicsCodes"):
                    naics_val = opp["naicsCodes"][0].get("code") if isinstance(opp["naicsCodes"][0], dict) else str(opp["naicsCodes"][0])
                url = opp.get("uiLink") or opp.get("additionalInfoLink") or opp.get("uri") or opp.get("solicitationUrl")

                opportunities.append(BidOpportunity(
                    bid_id=bid_id,
                    title=title,
                    posted_date=posted,
                    due_date=due,
                    agency=agency,
                    naics=naics_val,
                    portal="sam_gov",
                    url=url,
                    raw=opp,
                ))
            return opportunities
        except Exception as e:
            logger.exception(f"SAM.gov search failed: {e}")
            return []
