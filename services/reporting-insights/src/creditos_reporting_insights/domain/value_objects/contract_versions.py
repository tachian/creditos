from __future__ import annotations

import creditos_contracts

PROPOSAL_SUBMITTED_CONTRACT = "creditos://contracts/asyncapi/events/proposal/v1"
INTEGRATION_RESULT_SCHEMA_ID = (
    "https://contracts.creditos.local/schemas/integration/v1/integration-result.schema.json"
)
INTEGRATION_COST_SCHEMA_ID = (
    "https://contracts.creditos.local/schemas/integration/v1/integration-cost.schema.json"
)

PROPOSAL_EVENT_SCHEMA_VERSION = "v1"
INTEGRATION_SCHEMA_VERSION = "1.0"
INTERNAL_DTO_SCHEMA_VERSION = "internal-v1"

CONTRACTS_PACKAGE_MARKER = creditos_contracts.__name__

__all__ = [
    "CONTRACTS_PACKAGE_MARKER",
    "INTEGRATION_COST_SCHEMA_ID",
    "INTEGRATION_RESULT_SCHEMA_ID",
    "INTEGRATION_SCHEMA_VERSION",
    "INTERNAL_DTO_SCHEMA_VERSION",
    "PROPOSAL_EVENT_SCHEMA_VERSION",
    "PROPOSAL_SUBMITTED_CONTRACT",
]
