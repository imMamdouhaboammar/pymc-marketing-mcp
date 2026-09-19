"""Response Cohort Ledger domain package (RFC 003).

Provides:
- CustomerAcquisitionCohortLedger (and legacy ResponseCohortLedger alias)
- MediaResponseCohortLedger
- CustomerCohortRecord (and legacy CohortRecord alias)
- MediaResponseCohortRecord
"""

from marketing_mcp.domain.cohorts.contracts import (
    CohortRecord,
    CustomerAcquisitionCohortLedger,
    CustomerCohortRecord,
    MediaResponseCohortLedger,
    MediaResponseCohortRecord,
    PeriodType,
    ResponseCohortLedger,
)
from marketing_mcp.domain.cohorts.ledger import (
    build_cohort_ledger,
    build_media_response_cohort_ledger,
    extract_cohorts_from_transactions,
)

__all__ = [
    "CohortRecord",
    "CustomerAcquisitionCohortLedger",
    "CustomerCohortRecord",
    "MediaResponseCohortLedger",
    "MediaResponseCohortRecord",
    "PeriodType",
    "ResponseCohortLedger",
    "build_cohort_ledger",
    "build_media_response_cohort_ledger",
    "extract_cohorts_from_transactions",
]
