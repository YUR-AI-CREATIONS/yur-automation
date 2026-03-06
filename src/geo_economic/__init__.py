"""
Geo-Economic Intelligence Engine — identifies growth corridors.

Signals: migration, permits, infrastructure, employment, land prices.
Emits: corridor.signal_detected, metro.migration_shift, permit.acceleration.
"""

from .corridor_scanner import scan_corridors, score_region

__all__ = ["scan_corridors", "score_region"]
