How to read simulation plots
============================

The examples in the TQEC gallery often end with a logical error-rate plot.
Those plots summarize a complete simulation workflow: build a computation,
compile it into noisy detector-error-model circuits for several code distances,
sample those circuits, decode the samples, and estimate how often the decoded
observable disagrees with the expected observable.

The plot is meant to answer two questions:

* Is the computation operating below its threshold for the sampled noise model?
* How quickly does the logical error rate improve as the code distance grows?

Parts of the plot
-----------------

Most gallery plots use the physical error rate on the x-axis and the logical
error rate per shot on the y-axis. Both axes are usually logarithmic. Each
colored curve groups results with the same code distance, often stored in the
simulation metadata as ``d``.

The small ZX graph shown as an inset identifies the computation and observable
being sampled. The graph is the block-level representation of the spacetime
computation. Highlighted edges show one correlation surface: the logical
observable whose outcome is checked after decoding. If a gallery example has
multiple observables, TQEC plots one logical error-rate curve set per
observable.

How a point is computed
-----------------------

Each point in the plot is an empirical estimate computed from a batch of
samples. For a fixed physical error rate and code distance, TQEC performs the
following steps:

1. Build the block graph for the computation.
2. Select one correlation surface to use as the observable.
3. Compile the computation into a detector-error-model circuit for the chosen
   distance and noise model.
4. Sample the circuit with ``sinter`` until the configured shot or error budget
   is reached.
5. Decode each sample with the selected decoder.
6. Compare the decoded observable with the expected observable.
7. Report the logical error probability as the number of logical failures
   divided by the number of shots.

Because the estimate is statistical, the plotted value should be read together
with its confidence interval. More shots narrow the interval; fewer observed
failures widen it.

Threshold and below-threshold behavior
--------------------------------------

The threshold is the approximate physical error rate where increasing the code
distance stops helping. Below threshold, higher-distance curves should move
downward: the same physical error rate gives a lower logical error rate when
the code distance is increased. Above threshold, the curves cross or reorder
because the larger code no longer suppresses errors effectively under that
noise model.

On a log-log plot, the most important visual feature below threshold is the
asymptotic slope of the curves for different distances. A steeper downward
trend means that reducing the physical error rate, or increasing the code
distance, gives stronger logical error suppression. The absolute y-value still
matters, but the slope is what tells you whether the computation is scaling in
the desired direction.

Pseudo-threshold
----------------

A pseudo-threshold is a finite-size crossing point for two particular
distances, or for a particular logical error-rate target. It is useful for
comparing the sampled distances in one plot, but it is not the same as the
asymptotic threshold of a code family. Treat it as a practical landmark for the
specific computation, distances, decoder, and noise model being plotted.

Error suppression factor
------------------------

The error suppression factor, often written as :math:`\Lambda`, describes how
much the logical error rate improves when the distance is increased by a fixed
step in the below-threshold region. A larger :math:`\Lambda` means stronger
suppression. In practice, :math:`\Lambda` is inferred from ratios between
neighboring distance curves at the same physical error rate, after the curves
have entered their stable below-threshold scaling regime.

Confidence intervals and missing points
---------------------------------------

Logical error-rate estimates are binomial estimates. A symmetric standard
deviation is not always a good visual summary, especially when the number of
observed failures is small or the estimated probability is close to zero. TQEC
therefore uses interval estimates from the sampled task statistics instead of
assuming a symmetric error bar around the plotted value.

At very low physical error rates, confidence intervals can look large because
the simulation may observe only a few logical failures before it reaches the
configured shot budget. If no logical failures are observed, the logical error
rate is not proven to be zero; the run has only established an upper bound at
that sampling budget. Some points may be absent for the same reason: the
simulation did not collect enough failures or shots to produce a useful finite
estimate under the configured limits.

Reading gallery plots
---------------------

When reading a gallery plot, use this checklist:

* Identify the observable shown by the inset ZX graph.
* Read the x-axis as the physical error rate used by the noise model.
* Read the y-axis as the estimated logical error rate per shot.
* Compare curves at the same x-value to see whether larger distances reduce
  the logical error rate.
* Look for the crossing region to estimate where the sampled threshold lies.
* Focus on the below-threshold slope to judge error suppression.
* Check confidence intervals before drawing conclusions from isolated points.

These plots validate a computation when the expected below-threshold ordering
appears for the relevant observables and the inferred scaling matches the
intended code behavior.
