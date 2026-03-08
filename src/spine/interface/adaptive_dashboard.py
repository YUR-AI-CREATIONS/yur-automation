"""
Adaptive Dashboard — Self-configuring dashboards from domain profile.

Generates dashboard layouts, widgets, and data sources based on domain.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["DashboardWidget", "DashboardLayout", "AdaptiveDashboard"]


@dataclass
class DashboardWidget:
    """Dashboard widget definition."""

    widget_id: str
    widget_type: str
    title: str
    description: str = ""
    position: tuple[int, int] = (0, 0)
    size: tuple[int, int] = (1, 1)
    data_source: Optional[str] = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DashboardLayout:
    """Dashboard layout configuration."""

    layout_id: str
    layout_name: str
    description: str = ""
    grid_cols: int = 12
    grid_rows: int = 12
    widgets: list[DashboardWidget] = field(default_factory=list)


class AdaptiveDashboard:
    """
    Adaptive dashboard generator.

    Creates self-configuring dashboards based on domain profile.
    Widgets, data sources, and layout adapt to domain context.
    """

    def __init__(self, domain: str = "generic") -> None:
        self.domain = domain
        self.layouts: dict[str, DashboardLayout] = {}
        self.widgets: dict[str, DashboardWidget] = {}

    def register_widget(self, widget: DashboardWidget) -> None:
        """Register a dashboard widget."""
        self.widgets[widget.widget_id] = widget
        logger.debug(f"Registered widget: {widget.widget_id}")

    def create_layout(self, layout: DashboardLayout) -> None:
        """Create a dashboard layout."""
        self.layouts[layout.layout_id] = layout
        logger.debug(f"Created layout: {layout.layout_id}")

    def get_layout(self, layout_id: str) -> Optional[DashboardLayout]:
        """Retrieve a layout by ID."""
        return self.layouts.get(layout_id)

    def generate_domain_dashboard(self) -> DashboardLayout:
        """
        Generate a dashboard tailored to the domain.

        Returns a pre-configured layout with domain-specific widgets.
        """
        widgets = self._get_domain_widgets()
        layout = DashboardLayout(
            layout_id=f"{self.domain}_default",
            layout_name=f"{self.domain.capitalize()} Dashboard",
            grid_cols=12,
            grid_rows=12,
            widgets=widgets,
        )
        return layout

    def _get_domain_widgets(self) -> list[DashboardWidget]:
        """Get widgets for this domain."""
        domain_widgets = {
            "generic": [
                DashboardWidget(
                    widget_id="summary_stats",
                    widget_type="stats",
                    title="System Summary",
                    description="Overall system health and stats",
                    position=(0, 0),
                    size=(6, 2),
                    data_source="/api/metrics/summary",
                ),
                DashboardWidget(
                    widget_id="recent_tasks",
                    widget_type="table",
                    title="Recent Tasks",
                    description="Recently processed tasks",
                    position=(6, 0),
                    size=(6, 4),
                    data_source="/api/tasks",
                ),
                DashboardWidget(
                    widget_id="audit_log",
                    widget_type="timeline",
                    title="Audit Trail",
                    description="Recent audit events",
                    position=(0, 2),
                    size=(6, 4),
                    data_source="/api/audit",
                ),
            ],
            "construction": [
                DashboardWidget(
                    widget_id="project_summary",
                    widget_type="stats",
                    title="Active Projects",
                    description="Project count and status",
                    position=(0, 0),
                    size=(4, 2),
                    data_source="/api/grokstmate/status",
                ),
                DashboardWidget(
                    widget_id="sales_pipeline",
                    widget_type="chart",
                    title="Sales Pipeline",
                    description="Leads and opportunities",
                    position=(4, 0),
                    size=(4, 3),
                    data_source="/api/sales/pipeline",
                ),
                DashboardWidget(
                    widget_id="finance_summary",
                    widget_type="stats",
                    title="Finance Overview",
                    description="AR, AP, cashflow",
                    position=(8, 0),
                    size=(4, 2),
                    data_source="/api/finance/summary",
                ),
                DashboardWidget(
                    widget_id="project_controls",
                    widget_type="table",
                    title="Control Logs",
                    description="Change orders, documents, materials",
                    position=(0, 3),
                    size=(12, 4),
                    data_source="/api/project_controls/logs",
                ),
            ],
            "healthcare": [
                DashboardWidget(
                    widget_id="patient_stats",
                    widget_type="stats",
                    title="Patient Census",
                    description="Active patients and status",
                    position=(0, 0),
                    size=(6, 2),
                    data_source="/api/healthcare/patients",
                ),
                DashboardWidget(
                    widget_id="compliance_status",
                    widget_type="status",
                    title="Compliance Status",
                    description="HIPAA and audit status",
                    position=(6, 0),
                    size=(6, 2),
                    data_source="/api/healthcare/compliance",
                ),
                DashboardWidget(
                    widget_id="schedule",
                    widget_type="calendar",
                    title="Clinical Schedule",
                    description="Appointments and shifts",
                    position=(0, 2),
                    size=(12, 4),
                    data_source="/api/healthcare/schedule",
                ),
            ],
            "finance": [
                DashboardWidget(
                    widget_id="account_summary",
                    widget_type="stats",
                    title="Account Summary",
                    description="AR, AP, cash balance",
                    position=(0, 0),
                    size=(4, 2),
                    data_source="/api/finance/accounts",
                ),
                DashboardWidget(
                    widget_id="reconciliation_status",
                    widget_type="status",
                    title="Reconciliation Status",
                    description="Bank and ledger reconciliation",
                    position=(4, 0),
                    size=(4, 2),
                    data_source="/api/finance/reconciliation",
                ),
                DashboardWidget(
                    widget_id="audit_trail",
                    widget_type="timeline",
                    title="Audit Trail",
                    description="Financial transactions and approvals",
                    position=(8, 0),
                    size=(4, 3),
                    data_source="/api/audit",
                ),
                DashboardWidget(
                    widget_id="cashflow",
                    widget_type="chart",
                    title="Cashflow Forecast",
                    description="7-day and 30-day forecast",
                    position=(0, 3),
                    size=(12, 4),
                    data_source="/api/finance/cashflow/forecast",
                ),
            ],
        }

        return domain_widgets.get(self.domain, domain_widgets["generic"])

    def to_dict(self) -> dict[str, Any]:
        """Export dashboard config as dict."""
        return {
            "domain": self.domain,
            "layouts": {
                lid: {
                    "name": l.layout_name,
                    "description": l.description,
                    "grid_cols": l.grid_cols,
                    "grid_rows": l.grid_rows,
                    "widgets": [
                        {
                            "id": w.widget_id,
                            "type": w.widget_type,
                            "title": w.title,
                            "position": w.position,
                            "size": w.size,
                            "data_source": w.data_source,
                        }
                        for w in l.widgets
                    ],
                }
                for lid, l in self.layouts.items()
            },
        }
