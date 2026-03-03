"""
Call Handler Agent
Takes exploratory sales calls, qualifies leads, warm-transfers to you
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
import time

from core.trinity_client import TrinityClient
from core.config import SuperagentConfig


class CallFitLevel(str, Enum):
    """Lead fit classification"""
    NO_FIT = "no_fit"
    LOW_FIT = "low_fit"
    MEDIUM_FIT = "medium_fit"
    HIGH_FIT = "high_fit"


class CallHandler:
    """Autonomous inbound call handler agent"""
    
    # Qualification questions
    QUESTIONS = [
        {
            "question": "Hi! Thanks for calling Trinity Sales. I'm an AI assistant. Let me help qualify this quickly so we don't waste your time. First - how many decisions does your team make per day?",
            "follow_up": "And what's the approval process currently? Email chains, tools like Jira, or already automated?",
            "scoring": {
                "<50": 10,
                "50-200": 30,
                "200+": 50,
            }
        },
        {
            "question": "What's the cost of a one-day approval delay for you?",
            "follow_up": "Got it. And is this a priority in your 2026 budget?",
            "scoring": {
                "$0-5K": 10,
                "$5-50K": 30,
                "$50K+": 50,
            }
        },
        {
            "question": "Who else needs to be involved in this decision besides you?",
            "follow_up": "Perfect. Do you have their contact info so I can loop them in?",
            "scoring": {
                "just_me": 20,
                "2-3_people": 40,
                "5+_people": 30,  # Can be high decisions = good fit
            }
        },
    ]
    
    def __init__(self, phone_handler=None):
        """Initialize call handler
        
        Args:
            phone_handler: Twilio or similar phone API client
        """
        self.trinity = TrinityClient()
        self.phone_handler = phone_handler
        self.call_id = None
        self.prospect_data = {}
    
    async def handle_inbound_call(self, 
                                  from_number: str,
                                  call_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Main call handling logic"""
        
        start_time = time.perf_counter()
        call_result = {
            "from_number": from_number,
            "timestamp": datetime.now().isoformat(),
            "fit_level": CallFitLevel.NO_FIT,
            "lead_id": None,
            "action": "hangup",  # hangup, transfer_to_jeremy, schedule_followup
            "conversation": [],
        }
        
        try:
            # Answer call with greeting
            greeting = SuperagentConfig.CALL_HANDLER_GREETING
            await self._say(greeting)
            call_result["conversation"].append({"agent": greeting})
            
            # Run qualification loop
            fit_score = 0
            prospect_info = {}
            
            for question_set in self.QUESTIONS:
                # Ask question
                await self._say(question_set["question"])
                call_result["conversation"].append({"agent": question_set["question"]})
                
                # Listen for response
                response = await self._listen(timeout=10)
                call_result["conversation"].append({"prospect": response})
                
                # Score response
                score = await self._score_response(response, question_set)
                fit_score += score
                prospect_info.update(await self._extract_info(response))
                
                # Ask follow-up if low confidence
                if score < 20:
                    await self._say(question_set["follow_up"])
                    call_result["conversation"].append({"agent": question_set["follow_up"]})
                    
                    follow_response = await self._listen(timeout=10)
                    call_result["conversation"].append({"prospect": follow_response})
            
            # Determine fit level
            call_result["fit_level"] = self._calculate_fit_level(fit_score)
            self.prospect_data = prospect_info
            
            # Route based on fit
            if call_result["fit_level"] in [CallFitLevel.HIGH_FIT, CallFitLevel.MEDIUM_FIT]:
                # High fit -> warm transfer
                
                # Get prospect email if we have it
                if "email" in prospect_info:
                    lead = await self.trinity.create_lead(
                        name=prospect_info.get("name", "Unknown"),
                        email=prospect_info.get("email", ""),
                        company=prospect_info.get("company", "Unknown"),
                        title=prospect_info.get("title", "Unknown"),
                        source="phone_inbound",
                        metadata={
                            "call_fit_score": fit_score,
                            "fit_level": call_result["fit_level"],
                            "call_id": self.call_id,
                        }
                    )
                    call_result["lead_id"] = lead.get("id")
                
                # Warm transfer
                transfer_msg = SuperagentConfig.CALL_HANDLER_TRANSFER_PROMPT
                await self._say(transfer_msg)
                call_result["conversation"].append({"agent": transfer_msg})
                call_result["action"] = "transfer_to_jeremy"
                
                # In production: actually transfer call to you
                if self.phone_handler:
                    await self.phone_handler.transfer_call(SuperagentConfig.YOUR_PHONE)
            
            elif call_result["fit_level"] == CallFitLevel.LOW_FIT:
                # Low fit -> recommend alternative + collect info
                await self._say(
                    f"Sounds like Trinity might not be the perfect fit, but let me get your contact so we can follow up with some alternatives that might help."
                )
                call_result["action"] = "collect_info"
                
                # Get their contact
                email = await self._ask_for_email()
                prospect_info["email"] = email
                
                # Create lead for nurture
                if email:
                    lead = await self.trinity.create_lead(
                        name=prospect_info.get("name", "Unknown"),
                        email=email,
                        company=prospect_info.get("company", "Unknown"),
                        title=prospect_info.get("title", "Unknown"),
                        source="phone_inbound_nurture",
                        metadata={
                            "fit_level": "low_fit",
                            "nurture_type": "alternative",
                        }
                    )
                    call_result["lead_id"] = lead.get("id")
            
            else:
                # No fit -> polite ending
                await self._say(
                    "Thanks for calling! If your situation changes, feel free to reach out. Have a great day!"
                )
                call_result["action"] = "hangup"
            
            call_duration = max(0.0, time.perf_counter() - start_time)
            call_result["call_duration"] = call_duration

            # Log call to Trinity
            await self.trinity.log_interaction(
                lead_id=call_result.get("lead_id", "unknown"),
                interaction_type="inbound_call",
                content=f"Inbound call - Fit: {call_result['fit_level']}",
                metadata={
                    "fit_score": fit_score,
                    "prospect_info": prospect_info,
                    "call_duration": call_duration,
                }
            )
            
        except Exception as e:
            print(f"Error handling call: {e}")
            call_result["error"] = str(e)
            call_result["action"] = "hangup"
        
        return call_result
    
    def _calculate_fit_level(self, score: int) -> CallFitLevel:
        """Convert score to fit level"""
        if score >= 120:
            return CallFitLevel.HIGH_FIT
        elif score >= 80:
            return CallFitLevel.MEDIUM_FIT
        elif score >= 40:
            return CallFitLevel.LOW_FIT
        else:
            return CallFitLevel.NO_FIT
    
    # Phone interaction methods (stub implementations)
    
    async def _say(self, text: str) -> None:
        """Say text to prospect"""
        if self.phone_handler:
            await self.phone_handler.speak(text)
        print(f"[Agent]: {text}")
    
    async def _listen(self, timeout: int = 10) -> str:
        """Listen for prospect response"""
        if self.phone_handler:
            return await self.phone_handler.listen(timeout=timeout)
        return "[mock response]"
    
    async def _ask_for_email(self) -> str:
        """Ask for and collect email"""
        await self._say("Can I get your email to follow up?")
        return await self._listen(timeout=15)
    
    async def _score_response(self, response: str, question_set: Dict) -> int:
        """Score response to qualification question"""
        # In production: use AI to understand response
        # For MVP: simple keyword matching
        
        response_lower = response.lower()
        
        for key_phrase, points in question_set.get("scoring", {}).items():
            if any(word in response_lower for word in key_phrase.split("-")):
                return points
        
        return 10  # Default score
    
    async def _extract_info(self, response: str) -> Dict[str, str]:
        """Extract prospect info from response"""
        # In production: use AI to extract structured data
        return {}
    
    async def close(self):
        """Cleanup"""
        await self.trinity.close()
