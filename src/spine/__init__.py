"""
Universal Spine — Domain-agnostic core architecture.

Integrity, orchestration, and headless LLM layers form the immutable spine.
Distribution ports and interfaces plug into this foundation.
"""

from .integrity.governance_core import GovernanceCore, GovernanceScope, compute_governance_hash
from .integrity.audit_spine import AuditSpine
from .integrity.evidence_vault import EvidenceVault
from .orchestration.flow_registry import UniversalFlowRegistry
from .orchestration.universal_orchestrator import UniversalOrchestrator
from .orchestration.port_manager import PortManager
from .llm.headless_engine import HeadlessEngine
from .llm.customization_interface import CustomizationInterface
from .llm.prompt_registry import PromptRegistry
from .ports.data_port import DataPort
from .ports.task_port import TaskPort
from .ports.flow_port import FlowPort
from .ports.api_port import APIPort
from .flow.continuous_processor import ContinuousProcessor
from .flow.hub_collector import HubCollector
from .flow.distribution_manager import DistributionManager

__all__ = [
    "GovernanceCore",
    "GovernanceScope",
    "compute_governance_hash",
    "AuditSpine",
    "EvidenceVault",
    "UniversalFlowRegistry",
    "UniversalOrchestrator",
    "PortManager",
    "HeadlessEngine",
    "CustomizationInterface",
    "PromptRegistry",
    "DataPort",
    "TaskPort",
    "FlowPort",
    "APIPort",
    "ContinuousProcessor",
    "HubCollector",
    "DistributionManager",
]
