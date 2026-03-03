"""
Ouroboros Regeneration Engine — Self-Auditing, Self-Healing, Self-Spawning
The snake eating its tail: Trinity monitors itself, heals failures, spawns replacements
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)


class SystemHealth(Enum):
    """System health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    FAILED = "failed"


class HealStrategy(Enum):
    """Strategy for healing failed systems"""
    RETRY = "retry"  # Retry the same operation
    RESTART = "restart"  # Restart the subsystem
    ROLLBACK = "rollback"  # Rollback to previous state
    SPAWN_NEW = "spawn_new"  # Spawn a replacement system
    ESCALATE = "escalate"  # Escalate to human


@dataclass
class SystemHealthReport:
    """Health report for a system"""
    system_id: str
    system_name: str
    health_status: SystemHealth
    uptime_percentage: float
    last_error: Optional[str]
    error_count_24h: int
    last_check: str
    evidence_hash: str  # SHA256 of health data


@dataclass
class RegenerationEvent:
    """Event log for a regeneration action"""
    event_id: str
    system_id: str
    action: str
    reason: str
    strategy: HealStrategy
    timestamp: str
    success: bool
    evidence: Dict


class OuroborosSpine:
    """
    Self-regenerating Trinity backbone.
    
    Monitors all subsystems (YUR-AI, WAV, WCC, Sentinel, etc.)
    Detects failures, self-heals, and spawns replacements as needed.
    """

    def __init__(
        self,
        audit_interval_sec: int = 300,  # 5 minutes
        health_threshold: float = 0.95,  # 95% uptime = healthy
        max_retries: int = 3,
        regeneration_log_limit: int = 1000,
    ):
        self.audit_interval_sec = audit_interval_sec
        self.health_threshold = health_threshold
        self.max_retries = max_retries
        self.regeneration_log_limit = regeneration_log_limit
        
        # System inventory and health
        self.systems: Dict[str, Dict] = {}  # {system_id: {name, config, health}}
        self.health_history: Dict[str, List[SystemHealthReport]] = {}
        self.regeneration_events: List[RegenerationEvent] = []
        
        logger.info("🐍 Ouroboros Spine initialized (self-regenerating enabled)")

    def register_system(
        self,
        system_id: str,
        system_name: str,
        config: Dict,
    ) -> Tuple[bool, str]:
        """
        Register a subsystem for monitoring.
        
        Args:
            system_id: Unique ID (e.g., "yur_ai_001")
            system_name: Human name (e.g., "YUR-AI")
            config: System configuration with healthcheck endpoint, etc.
        
        Returns:
            (success, message)
        """
        if system_id in self.systems:
            return False, f"System {system_id} already registered"
        
        self.systems[system_id] = {
            "name": system_name,
            "config": config,
            "registered_at": datetime.utcnow().isoformat(),
            "health": SystemHealth.HEALTHY,
            "error_count": 0,
            "last_error": None,
        }
        
        self.health_history[system_id] = []
        
        logger.info(f"✅ Registered system: {system_id} ({system_name})")
        return True, f"System {system_id} registered"

    async def audit_loop(self):
        """
        Main audit loop: periodically check health of all systems.
        Runs as a background task.
        """
        logger.info(f"🔄 Ouroboros audit loop started (interval: {self.audit_interval_sec}s)")
        
        while True:
            try:
                logger.info("[Ouroboros] Audit cycle starting...")
                
                # Check health of all systems
                for system_id in self.systems:
                    health_report = await self._check_system_health(system_id)
                    await self._process_health_report(health_report)
                
                # Run regeneration checks
                await self._run_regeneration_checks()
                
                # Log summary
                summary = await self._get_audit_summary()
                logger.info(f"[Ouroboros] Audit complete: {summary}")
                
            except Exception as e:
                logger.error(f"[Ouroboros] Audit error: {e}")
            
            # Wait before next cycle
            await asyncio.sleep(self.audit_interval_sec)

    async def _check_system_health(self, system_id: str) -> SystemHealthReport:
        """Check health of a single system"""
        system = self.systems.get(system_id)
        if not system:
            return None
        
        try:
            # Query system healthcheck endpoint
            healthcheck_url = system["config"].get("healthcheck_url")
            if not healthcheck_url:
                return await self._create_health_report(system_id, SystemHealth.HEALTHY)
            
            # Simulate healthcheck (in production, make actual HTTP request)
            is_healthy = await self._query_healthcheck(healthcheck_url)
            
            health_status = SystemHealth.HEALTHY if is_healthy else SystemHealth.FAILING
            
            return await self._create_health_report(system_id, health_status)
        
        except Exception as e:
            logger.warning(f"Healthcheck error for {system_id}: {e}")
            return await self._create_health_report(system_id, SystemHealth.DEGRADED)

    async def _create_health_report(
        self,
        system_id: str,
        health_status: SystemHealth,
    ) -> SystemHealthReport:
        """Create a health report for a system"""
        system = self.systems[system_id]
        
        # Calculate uptime percentage (simplified)
        error_count = system.get("error_count", 0)
        uptime_percentage = max(0.0, 100.0 - (error_count * 2.0))  # Rough estimate
        
        # Generate evidence hash
        report_data = {
            "system_id": system_id,
            "health_status": health_status.value,
            "uptime_percentage": uptime_percentage,
            "timestamp": datetime.utcnow().isoformat(),
        }
        evidence_hash = hashlib.sha256(
            json.dumps(report_data, sort_keys=True).encode()
        ).hexdigest()
        
        report = SystemHealthReport(
            system_id=system_id,
            system_name=system["name"],
            health_status=health_status,
            uptime_percentage=uptime_percentage,
            last_error=system.get("last_error"),
            error_count_24h=error_count,
            last_check=datetime.utcnow().isoformat(),
            evidence_hash=evidence_hash,
        )
        
        # Store in history
        if system_id not in self.health_history:
            self.health_history[system_id] = []
        self.health_history[system_id].append(report)
        
        # Update system state
        self.systems[system_id]["health"] = health_status
        
        logger.info(f"[Ouroboros] Health check {system_id}: {health_status.value} "
                   f"({uptime_percentage:.1f}% uptime)")
        
        return report

    async def _process_health_report(self, report: SystemHealthReport):
        """Process a health report and decide if healing is needed"""
        if not report:
            return
        
        system_id = report.system_id
        
        if report.health_status == SystemHealth.HEALTHY:
            # All good, reset error count
            self.systems[system_id]["error_count"] = max(0, self.systems[system_id]["error_count"] - 1)
            return
        
        # System is degraded or failing
        self.systems[system_id]["error_count"] += 1
        self.systems[system_id]["last_error"] = report.last_error
        
        if report.health_status == SystemHealth.FAILING:
            # Attempt healing
            await self._attempt_healing(system_id)

    async def _attempt_healing(self, system_id: str):
        """Attempt to heal a failing system"""
        system = self.systems[system_id]
        error_count = system.get("error_count", 0)
        
        logger.warning(f"[Ouroboros] Healing attempt for {system_id} "
                      f"(error_count: {error_count})")
        
        # Decide healing strategy based on error count
        if error_count <= self.max_retries:
            strategy = HealStrategy.RETRY
        elif error_count <= self.max_retries + 1:
            strategy = HealStrategy.RESTART
        elif error_count <= self.max_retries + 2:
            strategy = HealStrategy.ROLLBACK
        else:
            # Too many failures, spawn replacement
            strategy = HealStrategy.SPAWN_NEW
        
        success = False
        
        if strategy == HealStrategy.RETRY:
            success = await self._retry_system(system_id)
        elif strategy == HealStrategy.RESTART:
            success = await self._restart_system(system_id)
        elif strategy == HealStrategy.ROLLBACK:
            success = await self._rollback_system(system_id)
        elif strategy == HealStrategy.SPAWN_NEW:
            success = await self._spawn_replacement(system_id)
        
        # Log regeneration event
        event = RegenerationEvent(
            event_id=self._generate_event_id(),
            system_id=system_id,
            action="healing",
            reason=f"Health status: {system.get('health', 'unknown')}",
            strategy=strategy,
            timestamp=datetime.utcnow().isoformat(),
            success=success,
            evidence={
                "error_count": error_count,
                "strategy": strategy.value,
            },
        )
        
        self.regeneration_events.append(event)
        if len(self.regeneration_events) > self.regeneration_log_limit:
            self.regeneration_events = self.regeneration_events[-self.regeneration_log_limit:]
        
        logger.info(f"[Ouroboros] Healing {'✅ succeeded' if success else '❌ failed'} "
                   f"for {system_id} using {strategy.value}")

    async def _retry_system(self, system_id: str) -> bool:
        """Retry operation on failing system"""
        logger.info(f"[Ouroboros] Retrying {system_id}...")
        # Simulate retry logic
        await asyncio.sleep(1)
        return True  # Assume success for now

    async def _restart_system(self, system_id: str) -> bool:
        """Restart a subsystem"""
        logger.info(f"[Ouroboros] Restarting {system_id}...")
        # In K8s, this would trigger a pod restart
        await asyncio.sleep(2)
        self.systems[system_id]["error_count"] = 0
        return True

    async def _rollback_system(self, system_id: str) -> bool:
        """Rollback to previous state"""
        logger.info(f"[Ouroboros] Rolling back {system_id}...")
        # Revert to last known good state
        await asyncio.sleep(2)
        return True

    async def _spawn_replacement(self, system_id: str) -> bool:
        """Spawn a replacement system"""
        logger.warning(f"[Ouroboros] 🐍 Spawning replacement for {system_id}...")
        system = self.systems[system_id]
        
        # Create new system instance
        new_system_id = f"{system_id}_replacement_{self._generate_suffix()}"
        
        success, msg = self.register_system(
            new_system_id,
            f"{system['name']} (replacement)",
            system["config"],
        )
        
        if success:
            logger.info(f"[Ouroboros] ✅ Spawned replacement: {new_system_id}")
            # Mark old system as deprecated
            system["deprecated"] = True
        
        return success

    async def _run_regeneration_checks(self):
        """Run additional regeneration checks"""
        # Check for systems that need rebalancing
        healthy_count = sum(
            1 for s in self.systems.values()
            if s.get("health") == SystemHealth.HEALTHY
        )
        total_count = len(self.systems)
        
        if total_count > 0:
            health_percentage = (healthy_count / total_count) * 100
            logger.info(f"[Ouroboros] System health: {health_percentage:.1f}% "
                       f"({healthy_count}/{total_count})")

    async def _query_healthcheck(self, url: str) -> bool:
        """Query a healthcheck endpoint (stub)"""
        # In production, make actual HTTP request
        import random
        return random.random() > 0.1  # 90% chance of being healthy

    async def _get_audit_summary(self) -> str:
        """Get summary of last audit cycle"""
        system_healths = {
            s: self.systems[s].get("health", "unknown").value
            for s in self.systems
        }
        return json.dumps(system_healths, indent=2)

    def get_regeneration_report(self) -> Dict:
        """Get full regeneration status and history"""
        return {
            "ouroboros_enabled": True,
            "audit_interval_sec": self.audit_interval_sec,
            "systems_monitored": len(self.systems),
            "systems": {
                sid: {
                    "name": s["name"],
                    "health": s.get("health", "unknown").value,
                    "error_count": s.get("error_count", 0),
                    "last_error": s.get("last_error"),
                }
                for sid, s in self.systems.items()
            },
            "recent_regeneration_events": [
                asdict(e) for e in self.regeneration_events[-10:]
            ],
        }

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return hashlib.sha256(
            f"{datetime.utcnow().isoformat()}:{len(self.regeneration_events)}".encode()
        ).hexdigest()[:12]

    def _generate_suffix(self) -> str:
        """Generate suffix for replacement systems"""
        import random
        return f"{random.randint(1000, 9999)}"


# Global instance
ouroboros_spine = OuroborosSpine(
    audit_interval_sec=300,  # 5 minutes
    health_threshold=0.95,
    max_retries=3,
)
