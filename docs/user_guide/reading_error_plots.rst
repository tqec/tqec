.. _reading_error_plots:

Reading logical error-rate plots
================================

The gallery examples and several user-guide pages display **logical error-rate
scaling plots** — the central diagnostic tool for evaluating a quantum
error-correcting computation.  This page explains every element of those plots
so that you can read them confidently, regardless of which computation or noise
model produced them.

If you have not yet seen the surface-code scaling law, start with
:ref:`surface_codes`; the key formula is reproduced below.


The example plot
----------------

Throughout this page we refer to the CNOT example from the
:doc:`gallery <../gallery/cnot>`.  The same reading applies to the
:doc:`memory <../gallery/memory>`, :doc:`move–rotation <../gallery/move_rotation>`,
:doc:`Steane encoding <../gallery/steane_encoding>`,
:doc:`three-CNOT <../gallery/three_cnots>` notebooks, and to the plots in
:doc:`detailed_plots` and :doc:`extended_stabilizers_implementation`.

A typical plot looks like this:

.. figure:: ../media/user_guide/reading_error_plots/cnot_logical_error_rate.png
   :align: center
   :alt: Logical CNOT error rate at distances d = 3, 5, 7

   Logical CNOT error rate as a function of the physical error rate,
   for code distances :math:`d \in \{3, 5, 7\}` under uniform depolarizing noise.
   The inset in the lower-left corner shows the ZX-graph of the computation with
   the measured observable highlighted.


Axes
----

Horizontal axis — physical error rate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **physical error rate** :math:`p` on the horizontal axis is the noise
strength injected into the compiled ``stim`` circuit.  Most examples use
:meth:`~tqec.utils.noise_model.NoiseModel.uniform_depolarizing`, which applies
a single-qubit depolarizing channel with rate :math:`p` after every gate,
measurement, and reset.  Any noise model parameterized by a single scalar
:math:`p` can be plotted the same way.

The axis is **logarithmic**, typically spanning :math:`10^{-4}` to
:math:`10^{-1}`.

Vertical axis — logical error rate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **logical error rate** :math:`p_L` on the vertical axis is the estimated
probability that one *shot* (one full run of the experiment) ends with an
incorrect decoded outcome for the observable under study.  Both axes are
logarithmic.

By default, :func:`sinter.plot_error_rate` reports this rate **per shot**.
Several gallery notebooks rescale the axis to an approximation of the logical
error rate **per QEC round** by passing
``failure_units_per_shot_func=lambda stat: stat.json_metadata["d"]``.
Check the *y*-axis label on the plot you are reading to determine which
convention is used.

Code distance
~~~~~~~~~~~~~

Each curve corresponds to one **code distance** :math:`d`.  In ``tqec``,
distances are generated from the scaling parameter :math:`k` through
:math:`d = 2k + 1`, so :math:`k = 1, 2, 3` gives :math:`d = 3, 5, 7`.


The ZX-graph inset
------------------

Most gallery plots include a small **ZX-graph** in the lower-left corner.
This is the spacetime diagram of the ``BlockGraph`` that was simulated,
obtained with :meth:`~tqec.block_graph.BlockGraph.to_zx_graph`.

**Node colors.**  Red nodes are :math:`X`-type spiders and blue nodes are
:math:`Z`-type spiders (see :ref:`Correlation Surface <terminology>`).

**Highlighted edges.**  The thick highlighted edges trace a
:ref:`correlation surface <terminology>` — the set of measurements whose
parity tracks how a logical operator is transformed from input to output.
The surface shown is the one passed to
:func:`~tqec.simulation.simulation.start_simulation_using_sinter`.  If you
change the observable or the computation, both the inset and the curves
change.

The inset is drawn by
:func:`~tqec.simulation.plotting.inset.plot_observable_as_inset`.  Some pages
(such as :doc:`detailed_plots`) show a threshold zoom inset instead of, or in
addition to, the ZX-graph.


How each point is computed
--------------------------

Every marker on a curve is estimated from many independent circuit shots.
For each pair :math:`(k, p)` — equivalently :math:`(d, p)` — the pipeline is:

1. **Compile.**  The ``BlockGraph`` is compiled at distance :math:`d`
   (scaling parameter :math:`k`) and exported to a noiseless ``stim`` circuit
   with detectors and logical observables.

2. **Inject noise.**  Noise at rate :math:`p` is added through the chosen
   noise-model factory (e.g.,
   :meth:`~tqec.utils.noise_model.NoiseModel.uniform_depolarizing`).

3. **Simulate.**  ``stim`` samples the noisy circuit and records detector
   syndromes and logical observable outcomes.

4. **Decode.**  A decoder — typically ``pymatching``
   :footcite:`Higgott_2023` — predicts the logical bit-flip from the
   syndromes.

5. **Compare.**  A mismatch between the decoder's prediction and the
   expected outcome counts as one logical error.

6. **Estimate.**  The logical error rate is the fraction of shots that
   produced a logical error, together with confidence bounds (see
   :ref:`error_plot_confidence`).

In code, this pipeline is orchestrated by
:func:`~tqec.simulation.simulation.start_simulation_using_sinter`, which
builds tasks with
:func:`~tqec.simulation.generation.generate_sinter_tasks` and collects
statistics via ``sinter``.  Sampling stops when ``max_shots`` and/or
``max_errors`` is reached.


Below and above threshold
-------------------------

Every QEC code has an **error threshold** :math:`p_\text{th}`: a physical
error rate below which increasing the distance suppresses the logical error
rate, and above which error correction is counterproductive.  The surface-code
scaling law (see :ref:`surface_codes`) is

.. math::

   p_L \;\propto\; \left(\frac{p}{p_\text{th}}\right)^{\lfloor (d+1)/2 \rfloor}
   \quad \text{for } p < p_\text{th}.

On a typical plot three regimes are visible:

**Below threshold.**
   At low :math:`p`, curves for larger :math:`d` lie *below* those for
   smaller :math:`d`.  On a log–log plot the below-threshold region often
   appears as a family of roughly parallel straight lines.

**Above threshold.**
   At high :math:`p`, all curves converge toward a logical error rate near
   :math:`1/2`.  Increasing :math:`d` no longer helps — the additional qubits
   introduce more errors than the code can correct.

**The crossing region.**
   Where curves for different distances meet gives a rough visual estimate of
   :math:`p_\text{th}` for that computation and noise model.  For a more
   precise value, use
   :func:`~tqec.simulation.threshold.binary_search_threshold` as
   demonstrated in :doc:`detailed_plots`.

The numerical ranges depend on the computation.  The CNOT example at the top
of this page crosses near :math:`p \sim 10^{-2}`; your computation may
differ.


.. _slope_below_threshold:

The slope below threshold
~~~~~~~~~~~~~~~~~~~~~~~~~

The most practically useful feature of a logical error-rate plot is the
**slope of each curve in the below-threshold region on the log–log plot**.
A steeper slope means that increasing :math:`d` suppresses logical errors
*faster* as :math:`p` is reduced.

From the scaling law above, the slope for distance :math:`d` is
approximately :math:`\lfloor (d+1)/2 \rfloor`.  When comparing two
implementations of the same computation, check both:

- The **vertical separation** at fixed :math:`p` — a constant shift suggests
  different overhead (e.g., a larger constant prefactor from extended
  stabilizers, as discussed in :doc:`extended_stabilizers_implementation`).
- Whether the **slopes match** — different slopes indicate a change in
  effective distance, which may point to a bug or a fundamental difference
  in the code structure.


Error suppression factor :math:`\Lambda`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **error suppression factor** :math:`\Lambda` quantifies how much the
logical error rate drops when the distance increases by two.  A practical
estimate at fixed :math:`p` well below threshold is

.. math::

   \Lambda \;\approx\; \frac{p_L(d)}{p_L(d + 2)}.

For an ideal surface code the power-law scaling predicts
:math:`\Lambda \approx (p_\text{th}/p)`, so :math:`\Lambda` grows as
:math:`p` decreases.  A measured :math:`\Lambda` much smaller than this
prediction suggests extra failure mechanisms — boundary effects, hook errors,
or decoder limitations — that reduce the expected suppression.

:math:`\Lambda` matters for **resource estimation**: knowing how fast
:math:`p_L` falls with :math:`d` tells you how large a code is needed at a
given hardware error rate to achieve a target logical error rate.


Pseudo-threshold
~~~~~~~~~~~~~~~~

For a *fixed* distance :math:`d`, the **pseudo-threshold** is the physical
error rate where the logical error rate of the encoded computation equals
the error rate of an unencoded qubit.  On a log–log plot with the diagonal
guide line :math:`p_L = p`, this is the point where the curve for distance
:math:`d` crosses that line.

Below the pseudo-threshold, the finite-distance encoded computation
suppresses errors relative to the baseline; above it, encoding offers no
benefit at that distance.

Unlike :math:`p_\text{th}`, a pseudo-threshold depends on the chosen
distance, circuit, decoder, noise model, and whether the plot reports
failures per shot or per round.  Treat it as a quick visual guide only.
To argue rigorously that a computation is below threshold, compare curves
across several distances or run a dedicated threshold search (see
:doc:`detailed_plots`).


.. _error_plot_confidence:

Confidence intervals and missing points
----------------------------------------

The shaded bands around each curve are **confidence regions** for the
binomial parameter being plotted on the *y*-axis.  They are *not* symmetric
Gaussian error bars.

``sinter.plot_error_rate`` uses :code:`sinter.fit_binomial`, which includes
all rates whose likelihood is within a factor ``max_likelihood_factor`` of
the maximum-likelihood estimate.  Because the logical error rate is bounded
in :math:`[0, 1]`, the intervals are naturally **asymmetric**, especially
near :math:`0` and :math:`1/2`.

Wide bands at low noise
~~~~~~~~~~~~~~~~~~~~~~~

**Wide bands at low** :math:`p` usually mean that few logical errors were
observed before sampling stopped.  Estimating a rate of :math:`10^{-6}` with
tight bounds requires either a very large number of shots or stopping only
after many errors; with modest ``max_errors``, little data is collected on
the left side of the plot.

Missing markers
~~~~~~~~~~~~~~~

**Missing markers** on the low-noise side typically mean that no logical
errors were recorded (``errors == 0``), so ``sinter.plot_error_rate``
omits the point, or that the corresponding simulation task did not finish.
The CNOT example at the top of this page is missing the :math:`d = 7`
point at :math:`p = 10^{-4}` for this reason.  Increasing ``max_shots``,
``max_errors``, or reusing a ``save_resume_filepath`` fills in the left
side of the plot at the cost of longer runs.

Duplicate markers
~~~~~~~~~~~~~~~~~

You may occasionally see **duplicate markers** at the same :math:`p`.  This
is a known plotting artifact tracked in `issue #825
<https://github.com/tqec/tqec/issues/825>`_.


Putting it all together
-----------------------

When you encounter a logical error-rate plot in the ``tqec`` documentation,
a good reading strategy is:

1. **Identify the computation** from the ZX-graph inset (or the surrounding
   text).  What observable is being measured?
2. **Locate the threshold** — the approximate crossing point of the curves.
   Is the physical error rate of interest below or above it?
3. **Compare slopes** across distances.  Do they match the expected
   :math:`\lfloor (d+1)/2 \rfloor` scaling?
4. **Estimate** :math:`\Lambda` from the vertical gap between adjacent
   curves at a fixed :math:`p` below threshold.
5. **Check the confidence bands.**  Wide bands or missing points indicate
   that the low-noise estimates are uncertain — more sampling may be needed
   for a definitive comparison.

For a hands-on walkthrough of generating such a plot from scratch, see the
:doc:`quick_start` guide.  For advanced plotting with threshold estimation,
see :doc:`detailed_plots`.


References
----------

.. footbibliography::
