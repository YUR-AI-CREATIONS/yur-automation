"""
Forensic & Remedy — failure collection, identification, remedy report.

Collects flow failures, audit anomalies. Produces remedy report for problem identification.
"""

from .failure_collector import record_failure, get_failures
from .remedy_report import generate_remedy_report

__all__ = ["record_failure", "get_failures", "generate_remedy_report"]
