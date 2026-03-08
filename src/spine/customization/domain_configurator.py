"""
Domain Configurator — Orchestrates LLM-driven domain setup.

Uses CustomizationInterface to generate and apply domain configurations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.spine.llm.customization_interface import (
    CustomizationInterface,
    CustomizationRequest,
)
from src.spine.config.universal_settings import UniversalSettings

logger = logging.getLogger(__name__)

__all__ = ["DomainConfigurator"]


class DomainConfigurator:
    """
    Orchestrates LLM-driven domain configuration.

    Generates industry-specific settings, profiles, and feature flags.
    """

    def __init__(self, customization_interface: Optional[CustomizationInterface] = None) -> None:
        self.customization = customization_interface or CustomizationInterface()

    def configure_domain(
        self,
        domain: str,
        business_description: str,
        folders: Optional[list[str]] = None,
    ) -> tuple[Optional[dict[str, Any]], str]:
        """
        Use LLM to generate domain configuration.

        Returns (config_dict, error_msg).
        """
        context = {
            "domain": domain,
            "business_description": business_description,
            "folders": folders or [],
        }

        request = CustomizationRequest(
            domain=domain,
            intent=f"Configure {domain} domain with settings, features, and governance rules",
            context=context,
            constraints=[
                "Generate valid YAML-serializable config",
                "Include data directory, governance scope, and enabled features",
                "Ensure domain-specific risk thresholds and authority levels",
            ],
        )

        result, err = self.customization.customize(request)
        if err:
            logger.error(f"Failed to configure domain: {err}")
            return None, err

        return result, ""

    def apply_domain_config(
        self, config: dict[str, Any], output_path: Optional[str] = None
    ) -> str:
        """
        Apply domain configuration.

        Writes to config/domains/{domain}.yaml or custom path.
        Returns path to written config.
        """
        domain = config.get("domain", "custom")

        if output_path is None:
            from pathlib import Path
            output_path = str(
                Path(__file__).resolve().parents[3]
                / "config"
                / "domains"
                / f"{domain}.yaml"
            )

        try:
            import yaml
            with open(output_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            logger.info(f"Applied domain config to {output_path}")
            return output_path
        except ImportError:
            logger.warning("PyYAML not installed; writing JSON instead")
            json_path = output_path.replace(".yaml", ".json")
            with open(json_path, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Applied domain config to {json_path}")
            return json_path
        except Exception as e:
            logger.error(f"Failed to apply domain config: {e}")
            raise

    def extract_domain_from_settings(
        self, settings: UniversalSettings
    ) -> dict[str, Any]:
        """Extract domain config from UniversalSettings."""
        return {
            "domain": settings.domain,
            "data_dir": str(settings.data_dir),
            "db_path": str(settings.db_path),
            "audit_jsonl_path": str(settings.audit_jsonl_path),
            "governance": {
                "default_authority_level": settings.default_authority_level,
                "default_governance_scope": settings.default_governance_scope,
                "risk_max_approval_amount": settings.risk_max_approval_amount,
                "rate_limit_per_hour": settings.rate_limit_per_hour,
                "max_cost_per_mission": settings.max_cost_per_mission,
            },
            "llm": {
                "ollama_first": settings.ollama_first,
                "ollama_model": settings.ollama_model,
                "openai_model": settings.openai_model,
                "embeddings_model": settings.embeddings_model,
            },
            "security": {
                "rbac_enabled": settings.rbac_enabled,
                "air_gap_mode": settings.air_gap_mode,
            },
        }
