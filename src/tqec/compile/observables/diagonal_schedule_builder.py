"""Observable builder for diagonal schedule convention.

Since observables are independent of the schedule used, we reuse the
fixed bulk observable builder for the diagonal schedule convention.
"""

from tqec.compile.observables.fixed_bulk_builder import FIXED_BULK_OBSERVABLE_BUILDER

# Observables are schedule-independent, so the diagonal convention can reuse
# the fixed-bulk observable builder unchanged.
DIAGONAL_SCHEDULE_OBSERVABLE_BUILDER = FIXED_BULK_OBSERVABLE_BUILDER
