"""Exact circuit distance, retaining correlated detector error mechanisms."""

import numpy as np
import stim
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array


def exact_circuit_distance(circuit: stim.Circuit) -> int:
    """Minimize faults subject to even detector and odd observable parity.

    Binary variables select error mechanisms; integer slack variables express
    parity constraints. This retains the original correlated flag symptoms.
    """
    dem = circuit.detector_error_model(decompose_errors=False).flattened()
    errors = [
        instruction
        for instruction in dem
        if isinstance(instruction, stim.DemInstruction) and instruction.type == "error"
    ]
    best = len(errors) + 1
    for observable in range(dem.num_observables):
        rows, columns, values = [], [], []
        num_checks = dem.num_detectors + 1
        for column, error in enumerate(errors):
            for target in error.targets_copy():
                assert isinstance(target, stim.DemTarget)
                if target.is_relative_detector_id():
                    rows.append(target.val)
                elif target.is_logical_observable_id() and target.val == observable:
                    rows.append(dem.num_detectors)
                else:
                    continue
                columns.append(column)
                values.append(1.0)
        rows.extend(range(num_checks))
        columns.extend(range(len(errors), len(errors) + num_checks))
        values.extend([-2.0] * num_checks)
        matrix = coo_array(
            (
                np.asarray(values, dtype=np.float64),
                (np.asarray(rows, dtype=np.int64), np.asarray(columns, dtype=np.int64)),
            ),
            shape=(num_checks, len(errors) + num_checks),
        ).tocsc()
        parity = np.zeros(num_checks)
        parity[-1] = 1
        cost = np.concatenate((np.ones(len(errors)), np.zeros(num_checks)))
        upper = np.concatenate((np.ones(len(errors)), np.full(num_checks, np.inf)))
        result = milp(
            cost,
            integrality=np.ones(len(cost), dtype=np.int64),
            bounds=Bounds(np.zeros(len(cost)), upper),
            constraints=LinearConstraint(matrix, parity, parity),
        )
        assert result.success, result.message
        best = min(best, round(result.fun))
    assert best <= len(errors), "No undetectable logical fault exists."
    return best
