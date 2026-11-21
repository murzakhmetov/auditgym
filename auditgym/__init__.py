"""auditgym: a reproducible RL environment for financial-audit agents.

Standard library only. See README.md and docs/DESIGN.md.
"""

__version__ = "0.4.0"
SCHEMA_VERSION = "auditgym/1.0"
CONFIG_VERSION = "1"

FINDING_TYPES = (
    "duplicate_invoice",
    "unallocated_payment",
    "wrong_fx_rate",
    "wrong_period",
)
