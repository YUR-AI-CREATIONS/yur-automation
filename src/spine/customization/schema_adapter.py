"""
Schema Adapter — Dynamic data model generation from natural language.

Generates JSON Schema, Pydantic models, and database schemas from descriptions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.spine.llm.customization_interface import (
    CustomizationInterface,
    CustomizationRequest,
)

logger = logging.getLogger(__name__)

__all__ = ["SchemaAdapter"]


class SchemaAdapter:
    """
    Generates data schemas dynamically.

    Converts business data requirements into JSON Schema, Pydantic models,
    and database table definitions.
    """

    def __init__(self, customization_interface: Optional[CustomizationInterface] = None) -> None:
        self.customization = customization_interface or CustomizationInterface()

    def generate_json_schema(
        self,
        data_description: str,
        domain: str = "generic",
    ) -> tuple[Optional[dict[str, Any]], str]:
        """
        Generate JSON Schema from description.

        Returns (schema_dict, error_msg).
        """
        context = {
            "data_description": data_description,
            "domain": domain,
        }

        request = CustomizationRequest(
            domain=domain,
            intent=f"Generate JSON Schema for: {data_description}",
            context=context,
            constraints=[
                "Output valid JSON Schema (draft 7)",
                "Include type, properties, required fields",
                "Add descriptions for each property",
                "Include examples",
            ],
        )

        result, err = self.customization.customize(request)
        if err:
            logger.error(f"Failed to generate JSON schema: {err}")
            return None, err

        if not result:
            return None, "No LLM response"

        try:
            if isinstance(result, dict) and "raw_response" in result:
                schema = json.loads(result.get("raw_response", "{}"))
            else:
                schema = result

            # Validate basic schema structure
            if not isinstance(schema, dict):
                return None, "Schema is not a dict"

            return schema, ""
        except Exception as e:
            logger.error(f"Failed to parse schema: {e}")
            return None, str(e)

    def generate_pydantic_model(
        self,
        data_description: str,
        domain: str = "generic",
    ) -> tuple[Optional[str], str]:
        """
        Generate Pydantic model code from description.

        Returns (model_code, error_msg).
        """
        context = {
            "data_description": data_description,
            "domain": domain,
        }

        request = CustomizationRequest(
            domain=domain,
            intent=f"Generate a Pydantic model for: {data_description}",
            context=context,
            constraints=[
                "Output valid Python code",
                "Use Pydantic BaseModel",
                "Include type hints",
                "Add field descriptions",
                "Include validators if appropriate",
            ],
        )

        result, err = self.customization.customize(request)
        if err:
            logger.error(f"Failed to generate Pydantic model: {err}")
            return None, err

        if not result:
            return None, "No LLM response"

        try:
            if isinstance(result, dict) and "raw_response" in result:
                code = result.get("raw_response", "")
            else:
                code = str(result)

            return code, ""
        except Exception as e:
            logger.error(f"Failed to extract Pydantic code: {e}")
            return None, str(e)

    def generate_sql_schema(
        self,
        entity_description: str,
        domain: str = "generic",
    ) -> tuple[Optional[str], str]:
        """
        Generate SQL table schema from description.

        Returns (sql_ddl, error_msg).
        """
        context = {
            "entity_description": entity_description,
            "domain": domain,
        }

        request = CustomizationRequest(
            domain=domain,
            intent=f"Generate SQL table schema for: {entity_description}",
            context=context,
            constraints=[
                "Output valid SQL CREATE TABLE statement",
                "Use SQLite syntax",
                "Include appropriate data types",
                "Add primary key and indexes",
                "Include constraints (NOT NULL, UNIQUE, etc.)",
            ],
        )

        result, err = self.customization.customize(request)
        if err:
            logger.error(f"Failed to generate SQL schema: {err}")
            return None, err

        if not result:
            return None, "No LLM response"

        try:
            if isinstance(result, dict) and "raw_response" in result:
                sql = result.get("raw_response", "")
            else:
                sql = str(result)

            return sql, ""
        except Exception as e:
            logger.error(f"Failed to extract SQL: {e}")
            return None, str(e)

    def generate_unified_model(
        self,
        data_description: str,
        domain: str = "generic",
    ) -> tuple[Optional[dict[str, Any]], str]:
        """
        Generate unified model definition (JSON Schema + Pydantic + SQL).

        Returns (model_bundle_dict, error_msg).
        """
        # Generate all three
        json_schema, err1 = self.generate_json_schema(data_description, domain)
        pydantic_code, err2 = self.generate_pydantic_model(data_description, domain)
        sql_schema, err3 = self.generate_sql_schema(data_description, domain)

        errors = [e for e in [err1, err2, err3] if e]
        if errors:
            logger.warning(f"Some models failed to generate: {errors}")

        return {
            "json_schema": json_schema,
            "pydantic_code": pydantic_code,
            "sql_schema": sql_schema,
            "errors": errors,
        }, ""
