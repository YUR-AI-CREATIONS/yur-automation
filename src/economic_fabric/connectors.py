"""
Economic Fabric — data connectors.

Census API, BLS, permit APIs. Return structured domain records.
When API key not set: return empty list + status. Ready for subscriptions.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from .domains import (
    CensusRecord,
    PermitRecord,
    MigrationRecord,
    EmploymentRecord,
    GDPRecord,
    InterestRateRecord,
)

_LOG = logging.getLogger("economic_fabric")

FABRIC_ROOT = Path(__file__).resolve().parents[2] / "data" / "fabric"
RAW_ECONOMIC = FABRIC_ROOT / "raw" / "economic"
CLEAN_ECONOMIC = FABRIC_ROOT / "clean" / "economic"


def _ensure_dirs() -> None:
    RAW_ECONOMIC.mkdir(parents=True, exist_ok=True)
    CLEAN_ECONOMIC.mkdir(parents=True, exist_ok=True)


def fetch_census(
    region_id: str,
    *,
    year: Optional[int] = None,
    api_key: Optional[str] = None,
) -> tuple[list[CensusRecord], dict[str, Any]]:
    """
    Fetch Census data for region. Uses CENSUS_API_KEY when set.
    Returns (records, status). status.available=False when no key.
    """
    api_key = (api_key or os.getenv("CENSUS_API_KEY") or "").strip()
    if not api_key:
        return [], {"available": False, "reason": "CENSUS_API_KEY not set", "connector": "census"}

    try:
        import urllib.request
        # Census API: https://api.census.gov/data/2021/acs/acs5
        base = os.getenv("CENSUS_API_BASE_URL", "https://api.census.gov/data")
        url = f"{base.rstrip('/')}/2021/acs/acs5?get=NAME,B01003_001E,B25077_001E,B25002_003E,B25002_001E&for=place:*&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        # Parse response; first row = headers
        records = []
        if isinstance(data, list) and len(data) > 1:
            headers = data[0]
            for row in data[1:]:
                if len(row) >= 4:
                    records.append(CensusRecord(
                        region_id=region_id,
                        year=2021,
                        population=int(row[1]) if row[1] else None,
                        median_income=float(row[2]) if row[2] else None,
                        vacancy_rate=float(row[3]) / float(row[4]) if row[3] and row[4] else None,
                        housing_units=int(row[4]) if row[4] else None,
                    ))
        return records[:100], {"available": True, "fetched": len(records), "connector": "census"}
    except Exception as e:
        _LOG.warning("census fetch failed: %s", e)
        return [], {"available": True, "error": str(e), "connector": "census"}


def fetch_permits(
    region_id: str,
    *,
    year: Optional[int] = None,
    api_key: Optional[str] = None,
) -> tuple[list[PermitRecord], dict[str, Any]]:
    """
    Fetch building permit data. Uses PERMITS_API_KEY or CENSUS building permits.
    """
    api_key = (api_key or os.getenv("CENSUS_API_KEY") or os.getenv("PERMITS_API_KEY") or "").strip()
    if not api_key:
        return [], {"available": False, "reason": "CENSUS_API_KEY or PERMITS_API_KEY not set", "connector": "permits"}

    try:
        import urllib.request
        base = os.getenv("CENSUS_API_BASE_URL", "https://api.census.gov/data")
        url = f"{base.rstrip('/')}/2022/permits?get=1-unit,2-units,3-4-units,5+-units&for=county:*&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        records = []
        if isinstance(data, list) and len(data) > 1:
            for row in data[1:]:
                if len(row) >= 5:
                    s1 = int(row[0] or 0)
                    s2 = int(row[1] or 0)
                    s34 = int(row[2] or 0)
                    s5 = int(row[3] or 0)
                    total = s1 + s2 * 2 + (s34 + s5) * 4
                    records.append(PermitRecord(
                        region_id=region_id,
                        year=2022,
                        single_family=s1,
                        multi_family=s2 + s34 + s5,
                        total_units=total,
                    ))
        return records[:100], {"available": True, "fetched": len(records), "connector": "permits"}
    except Exception as e:
        _LOG.warning("permits fetch failed: %s", e)
        return [], {"available": True, "error": str(e), "connector": "permits"}


def fetch_employment(
    region_id: str,
    *,
    year: Optional[int] = None,
    api_key: Optional[str] = None,
) -> tuple[list[EmploymentRecord], dict[str, Any]]:
    """
    Fetch BLS employment data. Uses BLS_API_KEY when set.
    """
    api_key = (api_key or os.getenv("BLS_API_KEY") or "").strip()
    if not api_key:
        return [], {"available": False, "reason": "BLS_API_KEY not set", "connector": "employment"}

    try:
        import urllib.request
        base = os.getenv("BLS_API_BASE_URL", "https://api.bls.gov/publicAPI/v2")
        payload = json.dumps({
            "seriesid": ["LAUST060000000000003", "LAUST060000000000004"],
            "startyear": str((year or 2023) - 1),
            "endyear": str(year or 2023),
            "registrationkey": api_key,
        }).encode()
        req = urllib.request.Request(
            f"{base.rstrip('/')}/timeseries/data/",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        records = []
        if isinstance(data, dict) and "Results" in data and "series" in data["Results"].get("series", []):
            for s in data["Results"]["series"][:5]:
                for d in s.get("data", [])[:12]:
                    month = int(d.get("period", "M01").replace("M", "")) if isinstance(d.get("period"), str) else None
                    records.append(EmploymentRecord(
                        region_id=region_id,
                        year=int(d.get("year", 0)),
                        month=month,
                        unemployed=int(d.get("value", 0)) if "03" in str(s.get("seriesID", "")) else None,
                        employed=int(d.get("value", 0)) if "04" in str(s.get("seriesID", "")) else None,
                    ))
        return records, {"available": True, "fetched": len(records), "connector": "employment"}
    except Exception as e:
        _LOG.warning("employment fetch failed: %s", e)
        return [], {"available": True, "error": str(e), "connector": "employment"}


def fetch_gdp(
    region_id: str,
    *,
    year: Optional[int] = None,
    api_key: Optional[str] = None,
) -> tuple[list[GDPRecord], dict[str, Any]]:
    """
    Fetch BEA GDP data. Uses BEA_API_KEY when set.
    """
    api_key = (api_key or os.getenv("BEA_API_KEY") or "").strip()
    if not api_key:
        return [], {"available": False, "reason": "BEA_API_KEY not set", "connector": "gdp"}

    try:
        import urllib.request
        base = os.getenv("BEA_API_BASE_URL", "https://apps.bea.gov/api")
        url = f"{base.rstrip('/')}/data/?UserID={api_key}&method=GetData&datasetname=Regional&TableName=CAGDP1&Year={(year or 2023)}&GeoFips=STATE&ResultFormat=JSON"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        records = []
        if isinstance(data, dict):
            for r in data.get("BEAAPI", {}).get("Results", {}).get("Data", [])[:50]:
                records.append(GDPRecord(
                    region_id=r.get("GeoFips", region_id),
                    year=int(r.get("TimePeriod", 0)),
                    gdp_millions=float(r.get("DataValue", 0)) if r.get("DataValue") else None,
                ))
        return records, {"available": True, "fetched": len(records), "connector": "gdp"}
    except Exception as e:
        _LOG.warning("gdp fetch failed: %s", e)
        return [], {"available": True, "error": str(e), "connector": "gdp"}


def fetch_interest_rates(
    region_id: str = "US",
    *,
    year: Optional[int] = None,
    api_key: Optional[str] = None,
) -> tuple[list[InterestRateRecord], dict[str, Any]]:
    """
    Fetch FRED interest rates. Uses FRED_API_KEY when set.
    """
    api_key = (api_key or os.getenv("FRED_API_KEY") or "").strip()
    if not api_key:
        return [], {"available": False, "reason": "FRED_API_KEY not set", "connector": "interest_rates"}

    try:
        import urllib.request
        base = os.getenv("FRED_API_BASE_URL", "https://api.stlouisfed.org/fred")
        series = ["FEDFUNDS", "MORTGAGE30US", "DGS10"]
        records = []
        for sid in series:
            url = f"{base.rstrip('/')}/series/observations?series_id={sid}&api_key={api_key}&file_type=json"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as r:
                obs = json.loads(r.read().decode())
            for o in obs.get("observations", [])[-12:]:
                val = o.get("value", ".")
                if val and val != ".":
                    rec = InterestRateRecord(region_id=region_id, year=int(o.get("date", "2023")[:4]))
                    if sid == "FEDFUNDS":
                        rec.fed_funds = float(val)
                    elif sid == "MORTGAGE30US":
                        rec.mortgage_30y = float(val)
                    elif sid == "DGS10":
                        rec.treasury_10y = float(val)
                    records.append(rec)
                    break
        return records, {"available": True, "fetched": len(records), "connector": "interest_rates"}
    except Exception as e:
        _LOG.warning("interest_rates fetch failed: %s", e)
        return [], {"available": True, "error": str(e), "connector": "interest_rates"}
