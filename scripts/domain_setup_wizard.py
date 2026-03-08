#!/usr/bin/env python3
"""
Domain Setup Wizard — Interactive industry configuration wizard.

Detects business context and sets up domain-specific env and configs.
"""

from __future__ import annotations

import sys
import os
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.spine.config.universal_settings import UniversalSettings
from src.spine.customization.domain_configurator import DomainConfigurator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def prompt(message: str, default: str = "") -> str:
    """Prompt user for input."""
    if default:
        message = f"{message} [{default}]: "
    else:
        message = f"{message}: "
    response = input(message).strip()
    return response or default


def prompt_choice(message: str, choices: list[str]) -> str:
    """Prompt user to choose from list."""
    print(f"\n{message}")
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")
    while True:
        response = input("Select (enter number): ").strip()
        try:
            idx = int(response) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print("Invalid selection, try again")


def main() -> int:
    """Run domain setup wizard."""
    print("\n" + "=" * 60)
    print("Universal Spine — Domain Setup Wizard")
    print("=" * 60 + "\n")

    print("This wizard will help you configure the Universal Spine")
    print("for your business domain.\n")

    # Step 1: Domain detection
    print("Step 1: Detect Business Domain")
    print("-" * 40)
    predefined_domains = ["construction", "healthcare", "finance", "generic"]
    domain = prompt_choice(
        "Which industry does your organization operate in?",
        predefined_domains,
    )
    print(f"\nSelected domain: {domain}\n")

    # Step 2: Business context
    print("Step 2: Business Context")
    print("-" * 40)
    business_name = prompt("Organization/project name", "My Organization")
    business_desc = prompt(
        "Describe your primary business process",
        "Business process description",
    )
    print()

    # Step 3: Data directories (optional)
    print("Step 3: Data Storage")
    print("-" * 40)
    default_data_dir = f"data/{domain}"
    data_dir = prompt("Data directory", default_data_dir)
    print()

    # Step 4: LLM configuration
    print("Step 4: LLM Configuration")
    print("-" * 40)
    llm_choice = prompt_choice(
        "Preferred LLM source?",
        ["Local Ollama (offline)", "OpenAI (cloud)"],
    )
    if llm_choice == "Local Ollama (offline)":
        ollama_first = "true"
        openai_key = ""
    else:
        ollama_first = "false"
        openai_key = prompt("OpenAI API key (optional)")
    print()

    # Step 5: Governance and risk
    print("Step 5: Governance & Risk")
    print("-" * 40)
    authority_level = prompt_choice(
        "Default authority level?",
        ["SEMI_AUTO", "AUTO", "MANUAL"],
    )
    governance_scope = prompt_choice(
        "Default governance scope?",
        ["internal", "external_low", "external_medium", "external_high", "restricted"],
    )
    print()

    # Step 6: Review and apply
    print("Step 6: Review Configuration")
    print("-" * 40)
    print(f"Domain: {domain}")
    print(f"Organization: {business_name}")
    print(f"Data directory: {data_dir}")
    print(f"LLM: {'Ollama (local)' if ollama_first == 'true' else 'OpenAI'}")
    print(f"Authority level: {authority_level}")
    print(f"Governance scope: {governance_scope}")
    print()

    confirm = prompt("Apply this configuration? (yes/no)", "yes")
    if confirm.lower() not in ("yes", "y"):
        print("Cancelled.")
        return 0

    # Apply configuration
    print("\nApplying configuration...\n")

    try:
        # Set environment variables
        os.environ["SPINE_DOMAIN"] = domain
        os.environ["SPINE_DATA_DIR"] = data_dir
        os.environ["SPINE_DEFAULT_AUTHORITY_LEVEL"] = authority_level
        os.environ["SPINE_DEFAULT_GOVERNANCE_SCOPE"] = governance_scope
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        os.environ["SPINE_OLLAMA_FIRST"] = ollama_first

        # Create settings
        settings = UniversalSettings(domain=domain)
        logger.info(f"Created settings for domain: {domain}")

        # Try to use LLM for advanced config
        try:
            logger.info("Generating domain configuration with LLM...")
            configurator = DomainConfigurator()
            config, err = configurator.configure_domain(
                domain=domain,
                business_description=business_desc,
                folders=[data_dir],
            )
            if config and not err:
                config_path = configurator.apply_domain_config(config)
                logger.info(f"Generated domain config: {config_path}")
            else:
                logger.warning(f"LLM configuration failed (optional): {err}")
        except Exception as e:
            logger.warning(f"LLM configuration not available: {e}")

        # Write .env file
        env_file = Path.home() / ".spinenv"
        with open(env_file, "w") as f:
            f.write(f"# Universal Spine Configuration for {domain}\n")
            f.write(f"SPINE_DOMAIN={domain}\n")
            f.write(f"SPINE_DATA_DIR={data_dir}\n")
            f.write(f"SPINE_DEFAULT_AUTHORITY_LEVEL={authority_level}\n")
            f.write(f"SPINE_DEFAULT_GOVERNANCE_SCOPE={governance_scope}\n")
            f.write(f"SPINE_OLLAMA_FIRST={ollama_first}\n")
            if openai_key:
                f.write(f"OPENAI_API_KEY={openai_key}\n")
        logger.info(f"Saved configuration to {env_file}")

        print("\n" + "=" * 60)
        print("Configuration Complete!")
        print("=" * 60)
        print(f"\nTo activate this configuration, run:")
        print(f"  source {env_file}  (or set env vars manually)")
        print(f"\nThen run universal bootstrap:")
        print(f"  python scripts/universal_bootstrap.py --domain {domain}")
        print()

        return 0

    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
