"""
Lead Prospector Agent
Finds 30-50 qualified leads daily from Apollo.io
"""

import asyncio
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime
from core.trinity_client import TrinityClient
from core.config import SuperagentConfig
import os
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET


class LinkedInProspector:
    """Autonomous lead prospecting agent using Apollo.io"""
    
    APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
    
    def __init__(self):
        self.trinity = TrinityClient()
        self.session = httpx.AsyncClient(timeout=30.0)
        self.apollo_key = os.getenv("APOLLO_API_KEY", SuperagentConfig.APOLLO_API_KEY if hasattr(SuperagentConfig, 'APOLLO_API_KEY') else "")
        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.apollo_key,
        }
        self._org_enrich_cache: Dict[str, Dict[str, Any]] = {}
        self._news_cache: Dict[str, List[str]] = {}
    
    async def find_prospects(self, 
                            industry: str = "fintech",
                            company_size: str = "20-500",
                            funding_min: int = 5,
                            limit: int = 50) -> List[Dict[str, Any]]:
        """Find prospect companies matching criteria using Apollo.io"""
        
        # Parse company size range
        try:
            min_emp, max_emp = map(int, company_size.split("-"))
        except:
            min_emp, max_emp = 20, 500
        
        prospects = await self._search_apollo_companies(
            industry=industry,
            min_employees=min_emp,
            max_employees=max_emp,
            limit=limit
        )
        
        print(f"[INFO] Apollo found {len(prospects)} prospect companies")
        return prospects
    
    async def get_decision_makers(self, company_domain: str) -> List[Dict[str, Any]]:
        """Find decision-makers at a company (CFO, VP Ops, CTO) using Apollo"""
        
        decision_maker_titles = [
            "CEO", "CTO", "CFO", "COO",
            "Chief Financial Officer",
            "Chief Technology Officer",
            "VP Operations", 
            "VP Engineering",
            "VP Finance",
            "Director of Engineering",
            "Head of Technology",
        ]
        
        makers = await self._search_apollo_people(
            company_domain=company_domain,
            titles=decision_maker_titles,
            limit=5
        )
        
        print(f"[INFO] Found {len(makers)} decision-makers at {company_domain}")
        return makers
    
    async def enrich_prospect(
        self,
        prospect_id: str,
        company_name: str,
        company_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enrich prospect with company data"""
        domain = self._normalize_domain(company_domain or "")

        enriched = {
            "company_id": prospect_id,
            "company_name": company_name,
            "company_domain": domain,
            "recent_news": await self._get_recent_news(company_name),
            "funding_info": await self._get_funding_info(domain) if domain else {},
            "company_size": await self._get_company_size(domain) if domain else 0,
            "technologies": await self._get_company_tech_stack(domain) if domain else [],
        }
        
        return enriched
    
    async def create_lead_from_prospect(self,
                                       person_name: str,
                                       person_title: str,
                                       person_email: str,
                                       company_name: str,
                                       enrichment: Dict[str, Any]) -> Dict[str, Any]:
        """Create Trinity lead from prospect data"""
        
        lead = await self.trinity.create_lead(
            name=person_name,
            email=person_email,
            company=company_name,
            title=person_title,
            source="linkedin-prospector",
            metadata={
                "funding_info": enrichment.get("funding_info"),
                "recent_news": enrichment.get("recent_news"),
                "company_size": enrichment.get("company_size"),
                "technologies": enrichment.get("technologies"),
                "score": await self._calculate_fit_score(enrichment),
            }
        )
        
        return lead
    
    async def run_daily_prospecting(self) -> Dict[str, Any]:
        """Run full daily prospecting cycle"""
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "prospects_found": 0,
            "leads_created": 0,
            "errors": [],
        }
        
        try:
            # Find prospects
            prospects = await self.find_prospects(limit=50)
            results["prospects_found"] = len(prospects)
            
            # For each prospect, get decision-makers, enrich, and create leads
            for prospect in prospects[:SuperagentConfig.DAILY_MAX_EMAILS]:
                try:
                    # Get decision-makers using company domain
                    company_domain = prospect.get("domain", "")
                    if not company_domain:
                        continue
                        
                    makers = await self.get_decision_makers(company_domain)
                    
                    # Enrich company data
                    enrichment = await self.enrich_prospect(
                        prospect.get("id", ""),
                        prospect["name"],
                        company_domain=company_domain,
                    )
                    
                    # Create Trinity leads
                    for maker in makers:
                        lead = await self.create_lead_from_prospect(
                            person_name=maker["name"],
                            person_title=maker["title"],
                            person_email=maker.get("email", ""),
                            company_name=prospect["name"],
                            enrichment=enrichment,
                        )
                        
                        if "id" in lead:
                            results["leads_created"] += 1
                            
                            # Trigger email sequence for new lead
                            await self.trinity.log_interaction(
                                lead_id=lead["id"],
                                interaction_type="lead_created",
                                content=f"Lead created from {prospect['name']}",
                                metadata={"source": "linkedin-prospector"}
                            )
                
                except Exception as e:
                    results["errors"].append(f"Error processing prospect {prospect.get('name')}: {str(e)}")
            
            print(f"[SUCCESS] Prospecting complete: {results['leads_created']} leads created")
            
        except Exception as e:
            results["errors"].append(f"Fatal error in prospecting: {str(e)}")
        
        return results
    
    # Helper methods - Apollo.io API implementations
    
    async def _search_apollo_companies(self, 
                                       industry: str,
                                       min_employees: int = 20,
                                       max_employees: int = 500,
                                       min_funding: int = 5_000_000,
                                       limit: int = 50) -> List[Dict[str, Any]]:
        """Search Apollo for companies matching criteria (free tier)"""
        try:
            payload = {
                "q_organization_keyword_tags": [industry],
                "organization_num_employees_ranges": [f"{min_employees},{max_employees}"],
                "per_page": min(limit, 25),
                "page": 1,
            }
            
            response = await self.session.post(
                f"{self.APOLLO_BASE_URL}/organizations/search",
                json=payload,
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                companies = data.get("organizations", [])
                print(f"[DEBUG] Apollo returned {len(companies)} companies")
                return [
                    {
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "domain": c.get("primary_domain"),
                        "industry": c.get("industry"),
                        "employee_count": c.get("estimated_num_employees"),
                        "linkedin_url": c.get("linkedin_url"),
                        "founded_year": c.get("founded_year"),
                    }
                    for c in companies
                ]
            else:
                print(f"[WARN] Apollo company search failed: {response.status_code} - {response.text[:200]}")
                return []
                
        except Exception as e:
            print(f"[ERROR] Apollo company search error: {e}")
            return []
    
    async def _search_apollo_people(self, 
                                    company_domain: str = None,
                                    titles: List[str] = None,
                                    limit: int = 10) -> List[Dict[str, Any]]:
        """Search Apollo for people (decision-makers) with emails.
        NOTE: People search requires Apollo paid plan. Returns empty on free tier."""
        try:
            payload = {
                "per_page": min(limit, 25),
                "page": 1,
            }
            
            if company_domain:
                payload["q_organization_domains"] = company_domain
            
            if titles:
                payload["person_titles"] = titles
            
            response = await self.session.post(
                f"{self.APOLLO_BASE_URL}/people/search",
                json=payload,
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                people = data.get("people", [])
                return [
                    {
                        "id": p.get("id"),
                        "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                        "first_name": p.get("first_name"),
                        "last_name": p.get("last_name"),
                        "title": p.get("title"),
                        "email": p.get("email"),
                        "linkedin_url": p.get("linkedin_url"),
                        "company": p.get("organization", {}).get("name"),
                        "company_domain": p.get("organization", {}).get("primary_domain"),
                    }
                    for p in people
                    if p.get("email")  # Only include people with emails
                ]
            elif response.status_code == 403:
                # Free tier doesn't have people search - return placeholder
                print(f"[INFO] Apollo people search requires paid plan. Using company domain as placeholder.")
                return []
            else:
                print(f"[WARN] Apollo people search failed: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[ERROR] Apollo people search error: {e}")
            return []
    
    async def _enrich_person(self, email: str) -> Optional[Dict[str, Any]]:
        """Enrich a person's data by email"""
        try:
            payload = {
                "email": email,
            }
            
            response = await self.session.post(
                f"{self.APOLLO_BASE_URL}/people/match",
                json=payload,
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json().get("person", {})
            return None
            
        except Exception as e:
            print(f"[ERROR] Apollo enrich error: {e}")
            return None

    async def _search_crunchbase(self, **kwargs) -> List[Dict[str, Any]]:
        """Search for companies - now uses Apollo"""
        return await self._search_apollo_companies(
            industry=kwargs.get("industry", "technology"),
            min_employees=20,
            max_employees=500,
            limit=kwargs.get("limit", 50)
        )
    
    async def _search_linkedin_people(self, **kwargs) -> List[Dict[str, Any]]:
        """Search for people - now uses Apollo"""
        company_id = kwargs.get("company_id", "")
        titles = kwargs.get("titles", [])
        
        # Apollo uses domain, not company_id, so we need to get the domain first
        return await self._search_apollo_people(
            company_domain=company_id,  # Assuming company_id is actually domain
            titles=titles,
            limit=10
        )
    
    async def _get_recent_news(self, company_name: str) -> List[str]:
        """Get recent company news"""
        name_key = (company_name or "").strip().lower()
        if not name_key:
            return []

        cached = self._news_cache.get(name_key)
        if cached is not None:
            return cached

        # Public, keyless signal source: Google News RSS
        # Example: https://news.google.com/rss/search?q=acme+when%3A30d&hl=en-US&gl=US&ceid=US:en
        query = quote_plus(f"{company_name} when:30d")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        try:
            resp = await self.session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Superagents; +https://yur-ai.com)"},
            )
            if resp.status_code != 200:
                self._news_cache[name_key] = []
                return []

            root = ET.fromstring(resp.text)
            items = root.findall(".//item")
            news: List[str] = []
            for item in items[:5]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if title and link:
                    news.append(f"{title} — {link}")
                elif title:
                    news.append(title)

            self._news_cache[name_key] = news
            return news
        except Exception:
            self._news_cache[name_key] = []
            return []
    
    async def _get_funding_info(self, company_domain: str) -> Dict[str, Any]:
        """Get funding information via Apollo organization enrichment"""
        domain = self._normalize_domain(company_domain)
        if not domain:
            return {}

        org = await self._apollo_org_enrich(domain)
        if not org:
            return {}

        total_funding = org.get("total_funding") or 0
        latest_stage = org.get("latest_funding_stage")
        latest_date = org.get("latest_funding_round_date")

        announcement = None
        if latest_stage:
            announcement = f"your {latest_stage} funding"
        elif total_funding:
            announcement = "your recent funding"

        return {
            "source": "apollo",
            "total_raised": total_funding,  # keep compatibility with fit scoring
            "total_funding": total_funding,
            "total_funding_printed": org.get("total_funding_printed"),
            "latest_funding_stage": latest_stage,
            "latest_funding_round_date": latest_date,
            "funding_events": org.get("funding_events") or [],
            "annual_revenue": org.get("annual_revenue"),
            "annual_revenue_printed": org.get("annual_revenue_printed"),
            "announcement": announcement,
        }
    
    async def _get_company_size(self, company_domain: str) -> int:
        """Get company headcount via Apollo organization enrichment"""
        domain = self._normalize_domain(company_domain)
        if not domain:
            return 0
        org = await self._apollo_org_enrich(domain)
        try:
            return int(org.get("estimated_num_employees") or 0) if org else 0
        except Exception:
            return 0
    
    async def _get_company_tech_stack(self, company_domain: str) -> List[str]:
        """Get company technology stack via Apollo organization enrichment"""
        domain = self._normalize_domain(company_domain)
        if not domain:
            return []

        org = await self._apollo_org_enrich(domain)
        if not org:
            return []

        techs: List[str] = []
        tech_names = org.get("technology_names") or []
        if isinstance(tech_names, list):
            techs.extend([t for t in tech_names if isinstance(t, str) and t.strip()])

        # Fallback: current_technologies is a list of objects with {name, category, ...}
        if not techs:
            current = org.get("current_technologies") or []
            if isinstance(current, list):
                for t in current:
                    if isinstance(t, dict):
                        name = (t.get("name") or "").strip()
                        if name:
                            techs.append(name)

        # De-dupe while preserving order
        seen = set()
        deduped: List[str] = []
        for t in techs:
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(t)

        return deduped[:50]

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain for Apollo endpoints (no scheme, no www, lowercase)."""
        if not domain:
            return ""
        d = domain.strip().lower()
        for prefix in ("https://", "http://"):
            if d.startswith(prefix):
                d = d[len(prefix):]
                break
        if d.startswith("www."):
            d = d[4:]
        d = d.split("/")[0].strip()
        return d

    async def _apollo_org_enrich(self, company_domain: str) -> Dict[str, Any]:
        """Apollo organization enrichment with simple in-memory caching."""
        domain = self._normalize_domain(company_domain)
        if not domain:
            return {}

        cached = self._org_enrich_cache.get(domain)
        if cached is not None:
            return cached

        if not self.apollo_key:
            self._org_enrich_cache[domain] = {}
            return {}

        try:
            resp = await self.session.get(
                f"{self.APOLLO_BASE_URL}/organizations/enrich",
                params={"domain": domain},
                headers=self.headers,
            )
            if resp.status_code == 200:
                org = (resp.json() or {}).get("organization") or {}
                self._org_enrich_cache[domain] = org
                return org

            self._org_enrich_cache[domain] = {}
            return {}
        except Exception:
            self._org_enrich_cache[domain] = {}
            return {}
    
    async def _calculate_fit_score(self, enrichment: Dict[str, Any]) -> float:
        """Calculate lead quality score (0-100)"""
        score = 0.0
        
        # Funded companies score higher
        if enrichment.get("funding_info", {}).get("total_raised", 0) > 5_000_000:
            score += 25
        
        # Growing companies score higher
        if enrichment.get("company_size", 0) > 50:
            score += 20
        
        # Recent news is positive signal
        if enrichment.get("recent_news"):
            score += 15
        
        # Tech stack match
        if any(tech in enrichment.get("technologies", []) 
               for tech in ["AWS", "Azure", "Python", "Microservices"]):
            score += 20
        
        return min(score, 100.0)
    
    async def close(self):
        """Cleanup"""
        await self.session.aclose()
        await self.trinity.close()
