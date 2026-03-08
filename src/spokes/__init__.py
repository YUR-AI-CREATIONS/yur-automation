"""
Spokes — domain-specific flows, plugins, and UIs that plug into the FranklinOps kernel.

Each spoke:
- Registers its own flows with the kernel
- Provides its own fleet plugins (optional)
- Can inject UI pages/persona into the hub
- Is fully decoupled from core OS logic

Spokes included:
- construction: Pay app tracking, project controls, construction-specific integrations
- sales: Lead capture, pipeline, opportunity ranking (JCK-focused currently)
- finance: AP/AR, cash flow, accounting integrations
- land_dev: Corridor scanning, deal simulation, land development pipeline
"""

__version__ = "0.1.0"
