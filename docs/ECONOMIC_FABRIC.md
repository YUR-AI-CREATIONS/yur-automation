# Economic Fabric — Sovereign Economic Intelligence Layer

The **Economic Fabric** is the full economic intelligence layer for Franklin OS. It aggregates Census, permits, migration, employment, GDP, interest rates, **plus nitty-gritty infrastructure**: traffic, healthcare, postal relocation, water/sewer lines, bridges, treatment plants, forestry, permit denials, compliance.

---

## Domains

### Core Economic
| Domain | Schema | Connector | Env Key |
|--------|--------|-----------|---------|
| **Census** | `CensusRecord` | Census API | `CENSUS_API_KEY` |
| **Permits** | `PermitRecord` | Census / Permits API | `CENSUS_API_KEY` or `PERMITS_API_KEY` |
| **Migration** | `MigrationRecord` | Census / IRS | `CENSUS_API_KEY` |
| **Employment** | `EmploymentRecord` | BLS | `BLS_API_KEY` |
| **GDP** | `GDPRecord` | BEA | `BEA_API_KEY` |
| **Interest Rates** | `InterestRateRecord` | FRED | `FRED_API_KEY` |

### Infrastructure (Nitty-Gritty)
| Domain | Schema | Ingest Via | Leading Signal |
|--------|--------|------------|----------------|
| **Traffic** | `TrafficRecord` | Data Fabric | ADT, congestion, yoy growth |
| **Healthcare** | `HealthcareRecord` | Data Fabric | Patient volume, beds, capacity |
| **Postal** | `PostalRecord` | Data Fabric | Relocation, address changes, mail volume |
| **Water** | `WaterInfrastructureRecord` | Data Fabric | Main lines, design capacity, projects |
| **Sewer** | `SewerInfrastructureRecord` | Data Fabric | Sewer lines, treatment capacity |
| **Bridges** | `BridgeRecord` | Data Fabric | Replacement, new construction |
| **Treatment Plants** | `TreatmentPlantRecord` | Data Fabric | Water + wastewater + sanitary |
| **Forestry** | `ForestryRecord` | Data Fabric | Permits, denials, compliance |
| **Permit Denials** | `PermitDenialRecord` | Data Fabric | Concrete, paper mills, hazardous |
| **Compliance** | `ComplianceRecord` | Data Fabric | Inspections, violations, new regs |
| **Economic Development** | `EconomicDevelopmentRecord` | Data Fabric | Incentives, rezoning, EDD projects |

---

## Indicators

| Indicator | Description | Used By |
|-----------|-------------|---------|
| **growth_index** | Composite: migration + permits + employment + GDP + infrastructure + migration_prediction | Geo-Economic, Pipeline |
| **migration_prediction_score** | Leading signals: postal, healthcare, traffic (before Census) | Growth index |
| **infrastructure_readiness** | Water, sewer, treatment plants, bridges, EDD | Growth index |
| **regulatory_risk_score** | Denials, compliance, forestry restrictions | Risk assessment |
| **demand_index** | Housing demand: population, vacancy, permits | Pipeline market_demand |
| **absorption_months** | Forecast: demand, permits, rates | Pipeline, Simulation |

---

## Ingest Schema (Data Fabric)

Ingest via `POST /api/data-fabric/ingest` with `source: "economic"`. Then normalize and build features. Include `region_id` in every row.

**Sample CSV columns for infrastructure:**
```csv
region_id,year,adt,yoy_growth_pct,patient_days,address_changes,main_line_miles,sewer_line_miles,plants_planned,denial_type,total_denials,compliance_strictness_score
texas_dallas,2024,45000,0.08,120000,5000,120.5,95.2,2,concrete_plant,1,0.3
```

**Key fields by domain:**
- **traffic**: adt, congestion_index, yoy_growth_pct
- **healthcare**: beds, patient_days, yoy_patient_growth_pct
- **postal**: facility_relocations, address_changes, mail_volume_yoy_pct, migration_proxy_score
- **water**: main_line_miles, design_capacity_mgd, projects_planned, projects_under_construction
- **sewer**: sewer_line_miles, treatment_capacity_mgd, plants_planned
- **permit_denials**: denial_type (concrete_plant|paper_mill|chemical|hazardous), total_denials, regulatory_shift_score
- **compliance**: new_regulations_adopted, compliance_strictness_score

---

## Data Flow

```
Connectors (Census, BLS, BEA, FRED) + Data Fabric (traffic, healthcare, postal, water, sewer, etc.)
         ↓
    fetch_*() → domain records
         ↓
    compute_region_scores() → EconomicRegion
         ↓
    get_economic_index(region_id)
         ↓
    Geo-Economic (corridor scanner)
    Pipeline (infrastructure, market_demand)
```

**Data Fabric path:** Ingest economic CSV/JSON via `POST /api/data-fabric/ingest` with `source: "economic"`. Normalize and build features. Economic Fabric reads from `data/fabric/features/economic/` and `data/fabric/clean/economic/`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/economic-fabric/index/{region_id}` | Get unified economic view |
| POST | `/api/economic-fabric/refresh` | Refresh index for regions |
| GET | `/api/economic-fabric/connectors` | Connector status (API keys) |

---

## Subscriptions to Add

| Service | Key | Signup |
|---------|-----|--------|
| Census API | `CENSUS_API_KEY` | https://api.census.gov/data/key_signup.html |
| BLS | `BLS_API_KEY` | https://www.bls.gov/developers/ |
| BEA | `BEA_API_KEY` | https://apps.bea.gov/API/signup/ |
| FRED | `FRED_API_KEY` | https://fred.stlouisfed.org/docs/api/api_key.html |

---

## Code

- `src/economic_fabric/domains.py` — Schemas
- `src/economic_fabric/connectors.py` — API fetchers
- `src/economic_fabric/indicators.py` — Growth, demand, absorption
- `src/economic_fabric/index.py` — Unified index, fabric load
