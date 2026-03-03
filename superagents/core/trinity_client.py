"""
Trinity API Client
Connects to https://yur-ai-api.onrender.com/
Handles all communication with Trinity backend.
"""

import httpx
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
from .config import SuperagentConfig


class TrinityClient:
    """Client for Trinity Render backend"""
    
    def __init__(self, base_url: str = "https://yur-ai-api.onrender.com", 
                 api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or SuperagentConfig.TRINITY_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        self.session_id = None
        
    async def health_check(self) -> bool:
        """Check if Trinity is healthy"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            print(f"Trinity health check failed: {e}")
            return False
    
    async def create_lead(self, 
                         name: str,
                         email: str,
                         company: str,
                         title: str,
                         source: str = "auto-prospector",
                         metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new lead in Trinity"""
        payload = {
            "name": name,
            "email": email,
            "company": company,
            "title": title,
            "source": source,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/leads",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error creating lead: {e}")
            return {"error": str(e)}
    
    async def update_lead(self, 
                         lead_id: str,
                         updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing lead"""
        try:
            response = await self.client.patch(
                f"{self.base_url}/api/leads/{lead_id}",
                json=updates,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error updating lead: {e}")
            return {"error": str(e)}
    
    async def get_lead(self, lead_id: str) -> Dict[str, Any]:
        """Get lead details"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/leads/{lead_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching lead: {e}")
            return {"error": str(e)}

    async def find_lead_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Best-effort lookup of a lead by email.

        This relies on the backend supporting query params on GET /api/leads.
        If unsupported, returns None without failing the scheduler loop.
        """
        email_norm = (email or "").strip().lower()
        if not email_norm:
            return None

        try:
            response = await self.client.get(
                f"{self.base_url}/api/leads",
                params={"email": email_norm},
                headers=self._get_headers(),
            )
            if response.status_code != 200:
                return None

            data = response.json()

            # Common shapes: lead dict, list of leads, or wrapper dict containing a list
            if isinstance(data, dict) and "id" in data and data.get("email"):
                return data

            candidates = None
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                for key in ("leads", "data", "items", "results"):
                    if isinstance(data.get(key), list):
                        candidates = data[key]
                        break

            if not candidates:
                return None

            for lead in candidates:
                if not isinstance(lead, dict):
                    continue
                if (lead.get("email") or "").strip().lower() == email_norm:
                    return lead

            return None
        except Exception as e:
            print(f"Error finding lead by email: {e}")
            return None
    
    async def create_opportunity(self,
                                lead_id: str,
                                title: str,
                                value: float,
                                stage: str = "discovery",
                                metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create sales opportunity from lead"""
        payload = {
            "lead_id": lead_id,
            "title": title,
            "value": value,
            "stage": stage,  # discovery, proposal, negotiation, closed
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/opportunities",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error creating opportunity: {e}")
            return {"error": str(e)}
    
    async def log_interaction(self,
                             lead_id: str,
                             interaction_type: str,
                             content: str,
                             metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Log lead interaction (email sent, call, etc)"""
        payload = {
            "lead_id": lead_id,
            "type": interaction_type,  # email, call, meeting, proposal_sent, etc
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/interactions",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error logging interaction: {e}")
            return {"error": str(e)}
    
    async def get_audit_trail(self, lead_id: str) -> List[Dict[str, Any]]:
        """Get complete interaction history for lead"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/leads/{lead_id}/audit-trail",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json().get("interactions", [])
        except Exception as e:
            print(f"Error fetching audit trail: {e}")
            return []
    
    async def execute_mission(self,
                             mission_type: str,
                             parameters: Dict[str, Any],
                             autonomy_level: str = "SEMI_AUTO") -> Dict[str, Any]:
        """Execute a mission through Trinity's Autonomy Gate
        
        autonomy_level options:
        - MANUAL: requires human approval
        - SEMI_AUTO: executes if criteria met, logs audit trail
        - FULL_AUTO: executes immediately (restricted scopes only)
        """
        payload = {
            "type": mission_type,
            "autonomy_level": autonomy_level,
            "parameters": parameters,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/missions",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error executing mission: {e}")
            return {"error": str(e)}
    
    async def get_governance_status(self) -> Dict[str, Any]:
        """Get current governance policies and rate limits"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/governance/status",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching governance status: {e}")
            return {}
    
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Superagent/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Convenience functions
async def get_trinity_client() -> TrinityClient:
    """Get initialized Trinity client"""
    return TrinityClient()
