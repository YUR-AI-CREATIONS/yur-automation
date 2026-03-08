"""
Workflow Generator — Generate flow specs from natural language.

Uses LLM to translate business process descriptions into executable flows.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.spine.llm.customization_interface import (
    CustomizationInterface,
    CustomizationRequest,
)
from src.core.flow_interface import FlowSpec, FlowDirection

logger = logging.getLogger(__name__)

__all__ = ["WorkflowGenerator"]


class WorkflowGenerator:
    """
    Generates flow specifications from natural language.

    Converts business process descriptions into executable FlowSpec objects.
    """

    def __init__(self, customization_interface: Optional[CustomizationInterface] = None) -> None:
        self.customization = customization_interface or CustomizationInterface()

    def generate_flow_spec(
        self,
        process_description: str,
        domain: str = "generic",
        direction: str = "INCOMING",
    ) -> tuple[Optional[FlowSpec], str]:
        """
        Use LLM to generate a flow spec from description.

        Returns (FlowSpec, error_msg).
        """
        context = {
            "process_description": process_description,
            "domain": domain,
            "direction": direction,
        }

        request = CustomizationRequest(
            domain=domain,
            intent=f"Generate a flow specification for: {process_description}",
            context=context,
            constraints=[
                "Output JSON with: flow_id, name, description, direction, input_schema, output_schema",
                "flow_id should be snake_case",
                "direction should be INCOMING, OUTGOING, or INTERNAL",
                "Include reasonable input/output schemas",
            ],
        )

        result, err = self.customization.customize(request)
        if err:
            logger.error(f"Failed to generate flow spec: {err}")
            return None, err

        if not result:
            return None, "No LLM response"

        try:
            flow_dict = result
            if isinstance(result, dict) and "raw_response" in result:
                flow_dict = json.loads(result.get("raw_response", "{}"))

            spec = FlowSpec(
                flow_id=flow_dict.get("flow_id", "generated_flow"),
                name=flow_dict.get("name", "Generated Flow"),
                description=flow_dict.get("description", ""),
                direction=FlowDirection[flow_dict.get("direction", "INCOMING")],
            )
            return spec, ""
        except Exception as e:
            logger.error(f"Failed to parse flow spec: {e}")
            return None, str(e)

    def generate_workflow_pipeline(
        self,
        pipeline_description: str,
        domain: str = "generic",
    ) -> tuple[Optional[list[FlowSpec]], str]:
        """
        Generate a multi-flow workflow pipeline.

        Returns (list of FlowSpecs, error_msg).
        """
        context = {
            "pipeline_description": pipeline_description,
            "domain": domain,
        }

        request = CustomizationRequest(
            domain=domain,
            intent=f"Generate a workflow pipeline: {pipeline_description}",
            context=context,
            constraints=[
                "Output JSON with array of flows",
                "Each flow has: flow_id, name, description, direction",
                "Order flows by execution sequence",
                "Include data transformations between flows",
            ],
        )

        result, err = self.customization.customize(request)
        if err:
            logger.error(f"Failed to generate workflow: {err}")
            return None, err

        if not result:
            return None, "No LLM response"

        try:
            flows_list = result
            if isinstance(result, dict) and "raw_response" in result:
                flows_list = json.loads(result.get("raw_response", "[]"))

            if not isinstance(flows_list, list):
                flows_list = flows_list.get("flows", [])

            specs = []
            for flow_dict in flows_list:
                spec = FlowSpec(
                    flow_id=flow_dict.get("flow_id", f"flow_{len(specs)}"),
                    name=flow_dict.get("name", "Generated Flow"),
                    description=flow_dict.get("description", ""),
                    direction=FlowDirection[flow_dict.get("direction", "INTERNAL")],
                )
                specs.append(spec)

            return specs, ""
        except Exception as e:
            logger.error(f"Failed to parse workflow: {e}")
            return None, str(e)

    def export_flow_specs(self, specs: list[FlowSpec]) -> dict[str, Any]:
        """Export flow specs as dict for registry registration."""
        return {
            "flows": [
                {
                    "flow_id": s.flow_id,
                    "name": s.name,
                    "description": s.description,
                    "direction": s.direction.name,
                }
                for s in specs
            ],
        }
