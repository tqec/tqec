"""Observable builder for diagonal schedule convention.

Since observables are independent of the schedule used, we reuse the
fixed bulk observable builder for the diagonal schedule convention.
"""

from tqec.compile.observables.fixed_bulk_builder import FIXED_BULK_OBSERVABLE_BUILDER

# Reuse the fixed bulk observable builder since observables don't depend on schedules
DIAGONAL_SCHEDULE_OBSERVABLE_BUILDER = FIXED_BULK_OBSERVABLE_BUILDER

