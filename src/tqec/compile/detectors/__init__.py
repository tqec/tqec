"""Defines code to automatically and efficiently compute detectors in a given time slice.

This module is crucial for ``tqec`` as it implements scalable functions to
automatically compute detectors in a provided time slice.

The implementation of this module is heavily based on sub-templates, that are
implemented in :mod:`tqec.templates.subtemplates`.

The main function defined by this module is
:func:`~.compute.compute_detectors_for_fixed_radius`. It allows to efficiently
compute all the detectors (represented as instances of
:class:`~.detector.Detector`) involving at least one of the measurements
contained in the last QEC round of the circuit that would be generated with
the provided :class:`~tqec.templates.base.Template` and
:class:`~tqec.plaquette.plaquette.Plaquette` instances.

Along with :func:`~.compute.compute_detectors_for_fixed_radius`, this module also
defines :class:`~.database.DetectorDatabase`. This is a class that is able to act
as a database for detectors and that can be used to:

- cache computations to avoid re-computing an already computed detector,
- ensure that the detectors in the final circuit are detectors from the provided
  database only (helps with reproducibility).

Implementation details can be found in the respective function/class
documentation.

"""

from .compute import (
    compute_detectors_for_fixed_radius as compute_detectors_for_fixed_radius,
)
from .database import DetectorDatabase as DetectorDatabase
from .detector import Detector as Detector
