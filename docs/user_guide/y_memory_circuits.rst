.. _y_memory_circuits:

Y basis memory circuits
=======================

This page explains the circuits of the :doc:`Y basis memory example </auto_examples/y_memory>`
and compares them with the circuits and data that Gidney published
:footcite:p:`Gidney_inplace_data_2022` for the construction of
:footcite:t:`Gidney_inplace_access_2024`.

X top and Z top
---------------

The two orientations measure a different corner in the :math:`Y` basis. The Z-top
circuit is the transpose of the X-top circuit, with the same gates in each tick.

.. list-table::
   :header-rows: 1

   * - Variant
     - Pipe
     - Top and bottom boundaries
     - Qubit measured in :math:`Y` (x, y; y points down)
   * - X top
     - ``ZXO``
     - :math:`X`
     - (0, d-1)
   * - Z top
     - ``XZO``
     - :math:`Z`
     - (d-1, 0)
   * - :footcite:t:`Gidney_inplace_data_2022`
     - n/a
     - :math:`X`
     - (0, 0)

Comparison with Gidney's circuits
---------------------------------

We compared a :math:`Y` memory with ``d`` rounds of an ordinary cube between the two Y
half cubes (``Y - ZXZ - Y`` for X top, ``Y - XZZ - Y`` for Z top) and ``d // 2`` padding
rounds with Gidney's circuits for ``r = d`` and ``rb = d // 2``
:footcite:p:`Gidney_inplace_data_2022`. All circuits use the CZ gate set and the SI1000
noise model of Gidney :footcite:p:`Gidney_si1000_2021`. All were decoded with correlated
PyMatching (``pymatching-correlated`` in ``sinter``), to about 1000 logical errors per
point. This simulation takes hours, so its results are shown in the table below. The
table compares each tqec circuit with Gidney's circuit decoded by the same decoder. It
does not use Gidney's published numbers. They come from a decoder that is not public.

.. list-table:: Logical error rate of tqec divided by the logical error rate of Gidney's circuit with the same decoder
   :header-rows: 1

   * - p
     - d = 3
     - d = 5
     - d = 7
     - d = 9
   * - 0.001, X top
     - 0.98
     - 1.01
     - 1.04
     - 0.97
   * - 0.001, Z top
     - 1.07
     - 0.98
     - 1.08
     - 0.98
   * - 0.003, X top
     - 1.05
     - 1.03
     - 1.02
     - 1.03
   * - 0.003, Z top
     - 0.98
     - 1.06
     - 1.08
     - 1.01

Each ratio has a standard error of 0.04 to 0.05. The two orientations have the same
logical error rate as each other and as Gidney's circuits. They also have the same number
of detectors, measurements and CZ gates as Gidney's circuits, and a graphlike distance
(``shortest_graphlike_error``) of ``d``.

.. note::
   With the padding of the paper (``d // 2`` padding rounds on each side), Gidney's
   published circuit at ``d = 7`` has a logical error made of 6 faults, so its circuit
   distance is at most 6, not 7. Gidney's source mentions this
   :footcite:p:`Gidney_inplace_data_2022`. A ``tqec`` circuit matched to Gidney's layout
   and noise has the same 6-fault logical error in both orientations (X top and Z top).

The table below links the ``d=3`` circuits of the comparison (noiseless, CZ gate set).
The sections that follow give the ticks to look at with the Crumble tick slider.

.. list-table::
   :header-rows: 1

   * - Circuit
     - CZ gate set
     - Native gates
   * - Gidney
     - `open <gcz_>`__ (93 ticks)
     - `open <gna_>`__ (58 ticks)
   * - tqec X top
     - `open <xcz_>`__ (96 ticks)
     - `open <xna_>`__ (60 ticks)
   * - tqec Z top
     - `open <zcz_>`__ (96 ticks)
     - `open <zna_>`__ (60 ticks)

Differences
-----------

The ``tqec`` circuits and Gidney's circuits are not identical gate for gate. None of the
differences below changes the logical error rate of the :math:`Y` memory.

.. list-table::
   :header-rows: 1

   * - Difference
     - Gidney
     - tqec
   * - CZ ticks in a memory round
     - 4
     - 5 in ordinary cubes, 4 in the Y half cube
   * - Transition round
     - same CZ moments, single-qubit gates in other moments
     - same CZ moments, single-qubit gates in other moments
   * - Corner measured in :math:`Y`
     - (0, 0)
     - (0, d-1) or (d-1, 0)
   * - Observable
     - an L along two edges
     - two midlines that cross at the centre
   * - Readout of the other data qubits
     - split on the anti-diagonal
     - split on the main diagonal
   * - Qubits declared at ``d=3`` (comparison circuits)
     - 19
     - 35, of which 19 are used

CZ schedule
~~~~~~~~~~~

A memory round of Gidney's circuit has 4 CZ ticks. A round of an ordinary ``tqec`` cube
has 5, with the same number of CZ gates. The fixed-bulk plaquettes use the CZ schedules
``(1, 4, 3, 5)`` and ``(1, 2, 3, 5)``. The Y half cube copies Gidney's rounds, so its own
rounds keep 4 CZ ticks. At ``d=3`` the CZ ticks of each round of the :math:`Y` memory are
4, 4, 5, 5, 5, 5, 5, 4, 4 in ``tqec`` and 4, 4, 5, 4, 4, 4, 5, 4, 4 in Gidney's circuit.
The extra tick adds one idle moment to each round of an ordinary cube.

This has no measurable effect on the :math:`Y` memory. For the :math:`X` and :math:`Z`
memories at ``d=9`` and ``p=0.001``, the ``tqec`` circuits have 1.07 ± 0.03 (X) and
1.13 ± 0.03 (Z) times the logical error rate of Gidney's circuits (about 3000 logical
errors for each circuit). We did not confirm that the extra tick is the cause.

Crumble: ticks 32 to 41 of `Gidney <gcz_>`__ and ticks 32 to 42 of
`tqec X top <xcz_>`__.

Transition round
~~~~~~~~~~~~~~~~

The five CZ moments of the transition round are the same in all three circuits (2, 5, 8,
6 and 6 CZ gates at ``d=3``). The single-qubit gates are in different moments: ``tqec``
writes the transition with ``CX``, ``CY`` and ``S`` gates, and the conversion to the CZ
gate set moves the resulting single-qubit gates. The diagonal domain wall starts at the
corner measured in :math:`Y`, so it is on a different diagonal in each circuit.

Crumble: ticks 20 to 31 of `Gidney <gcz_>`__, `tqec X top <xcz_>`__ and
`tqec Z top <zcz_>`__. The circuits with native gates show the ``S`` gates:
`Gidney <gna_>`__, `tqec X top <xna_>`__, `tqec Z top <zna_>`__.

Observable
~~~~~~~~~~

Gidney's :math:`Y` observable is :math:`Y` on the corner, :math:`Z` along the top row and
:math:`X` along the left column: an L. The ``tqec`` observable is made from measurements
of the transition round, and its support is two midlines that cross at the centre. At
``d=3`` the observable includes 10 measurements in Gidney's circuit and 5 in ``tqec``.
Both are representatives of logical :math:`Y` with circuit distance ``d``. Crumble shows
the observable in its detector panel.

Readout
~~~~~~~

In the last round each data qubit except the :math:`Y` corner is measured in :math:`X` or
:math:`Z`. Gidney measures :math:`Z` where ``x + y < d`` and :math:`X` elsewhere. ``tqec``
X top measures :math:`X` where ``x <= y`` and :math:`Z` elsewhere, and Z top measures
:math:`Z` where ``x < y`` and :math:`X` elsewhere. The split follows the domain wall,
which starts at the :math:`Y` corner.

Crumble: the last ``M`` layer, tick 93 of `Gidney <gcz_>`__ and tick 96 of
`tqec X top <xcz_>`__.

Unused qubits
~~~~~~~~~~~~~

A ``tqec`` circuit declares qubits that no gate uses. They have a ``QUBIT_COORDS`` line
and idle noise, but no reset, gate or measurement. At ``d=3`` the :math:`X` memory
declares 25 qubits and uses 17, and the :math:`Y` memory of the comparison declares 35
and uses 19. There are two sources:

- a plaquette with no gates keeps its syndrome qubit. This is also true for the
  :math:`X` and :math:`Z` memories on ``main``,
- each plaquette of the Y half cube declares all four data qubits, also when it uses
  only two.

The detector error model does not change when these qubits are removed, and the sampling
time changes by less than 6%. But ``stim.Circuit.num_qubits`` counts them: at ``d=9`` it
is 12% too high for the :math:`X` memory (181 against 161) and 27% too high for the
:math:`Y` memory (215 against 169). Count only the qubits that gates use when you compare
qubit counts with other circuits.

.. _gcz: https://algassert.com/crumble#circuit=Q(0,0)0;Q(0,1)1;Q(0,2)2;Q(1,0)3;Q(1,1)4;Q(1,2)5;Q(2,0)6;Q(2,1)7;Q(2,2)8;Q(-0.5,1.5)9;Q(0.5,-0.5)10;Q(0.5,0.5)11;Q(0.5,1.5)12;Q(1.5,-0.5)13;Q(1.5,0.5)14;Q(1.5,1.5)15;Q(1.5,2.5)16;Q(2.5,0.5)17;Q(2.5,1.5)18;R_15_13_11_9_6_4_3_2_1_8_7_5_18_16_14_12;TICK;H_2_4_5_9_11_12_13_14_15_16_18;TICK;CZ_1_11_2_12_3_13_4_14_5_15_8_18;TICK;H_1_2_3_4_5_8;TICK;CZ_4_15_5_12_7_14;TICK;CZ_1_12_2_9_3_14_4_11_5_16_6_13_7_18_8_15;TICK;H_1_2_3_4_5_6_7_8_13_18;TICK;CZ_1_9_3_11_4_12_6_14_7_15_8_16;TICK;H_6_7_9_11_12_14_15_16;TICK;M_15_13_11_9_18_16_14_12;DT(-0.5,1.5,0)rec[-5];DT(0.5,0.5,0)rec[-6];DT(1.5,-0.5,0)rec[-7];DT(1.5,2.5,0)rec[-3];DT(2.5,1.5,0)rec[-4];SHIFT_COORDS(0,0,1);TICK;R_15_13_11_9_18_16_14_12;TICK;H_9_11_12_13_14_15_16_18;TICK;CZ_1_11_2_12_3_13_4_14_5_15_8_18;TICK;H_1_2_3_4_5_8;TICK;CZ_4_15_5_12_7_14;TICK;CZ_1_12_2_9_3_14_4_11_5_16_6_13_7_18_8_15;TICK;H_1_3_4_6_7_8_13_18;TICK;CZ_1_9_3_11_4_12_6_14_7_15_8_16;TICK;H_6_9_11_12_14_15_16;TICK;M_15_13_11_9_18_16_14_12;DT(-0.5,1.5,0)rec[-13]_rec[-5];DT(0.5,0.5,0)rec[-14]_rec[-6];DT(0.5,1.5,0)rec[-9]_rec[-1];DT(1.5,-0.5,0)rec[-15]_rec[-7];DT(1.5,0.5,0)rec[-10]_rec[-2];DT(1.5,1.5,0)rec[-16]_rec[-8];DT(1.5,2.5,0)rec[-11]_rec[-3];DT(2.5,1.5,0)rec[-12]_rec[-4];SHIFT_COORDS(0,0,1);TICK;R_15_13_11_10_9_0_18_17_16_14_12;TICK;C_ZYX_11_15;H_9_10_12_13_16;SQRT_X_0_14_18;TICK;CZ_4_14_8_18;TICK;CZ_1_9_3_13_4_12_7_17_8_16;TICK;C_XYZ_4_8;C_ZYX_14_18;H_1_3_7_17;TICK;CZ_1_12_2_9_3_14_4_11_5_16_6_13_7_18_8_15;TICK;C_ZYX_8;H_1_2_3_6_7_9_13_14_16_18;SQRT_X_4;TICK;CZ_0_11_3_10_4_15_5_12_6_17_7_14;TICK;H_0_3_4_5_6_7;TICK;CZ_0_10_1_11_2_12_4_14_5_15_7_17;TICK;H_0_2_5_10_11_12_14_15_17;TICK;M_18_17_15_11_9_16_14_13_12_10;DT(-0.5,1.5,0)rec[-15]_rec[-6];DT(0.5,0.5,0)rec[-16]_rec[-7]_rec[-1];DT(0.5,1.5,0)rec[-11]_rec[-2];DT(1.5,-0.5,0)rec[-17]_rec[-3];DT(1.5,0.5,0)rec[-12]_rec[-9];DT(1.5,1.5,0)rec[-18]_rec[-8]_rec[-4];DT(1.5,2.5,0)rec[-13]_rec[-5];DT(2.5,1.5,0)rec[-14]_rec[-10];OI(0)rec[-10]_rec[-9]_rec[-5]_rec[-2];SHIFT_COORDS(0,0,1);TICK;R_10_12_14_16_9_11_15_17;TICK;H_9_10_11_12_14_15_16_17;TICK;CZ_1_9_3_11_4_12_6_14_7_15_8_16;TICK;H_1_3_4_6_7_8;TICK;CZ_1_12_2_9_3_14_4_11_5_16_8_15;TICK;CZ_0_11_3_10_4_15_5_12_6_17_7_14;TICK;H_0_1_2_3_4_5_7_9;TICK;CZ_0_10_1_11_2_12_4_14_5_15_7_17;TICK;H_0_2_4_10_11_12_14_15_16_17;TICK;M_10_12_14_16_9_11_15_17;DT(-0.5,1.5,0)rec[-14]_rec[-4];DT(0.5,-0.5,0)rec[-9]_rec[-8];DT(0.5,0.5,0)rec[-15]_rec[-3];DT(0.5,1.5,0)rec[-10]_rec[-7];DT(1.5,0.5,0)rec[-12]_rec[-11]_rec[-6];DT(1.5,1.5,0)rec[-18]_rec[-16]_rec[-2];DT(1.5,2.5,0)rec[-13]_rec[-5];DT(2.5,0.5,0)rec[-17]_rec[-1];SHIFT_COORDS(0,0,1);TICK;REPEAT_2_{;R_10_12_14_16_9_11_15_17;TICK;H_4_6_8_9_10_11_12_14_15_16_17;TICK;CZ_1_9_3_11_4_12_6_14_7_15_8_16;TICK;H_1_3_4_5_6_7_8;TICK;CZ_1_12_2_9_3_14_4_11_5_16_8_15;TICK;CZ_0_11_3_10_4_15_5_12_6_17_7_14;TICK;H_0_1_2_3_4_5_7_9;TICK;CZ_0_10_1_11_2_12_4_14_5_15_7_17;TICK;H_0_2_4_10_11_12_14_15_16_17;TICK;M_10_12_14_16_9_11_15_17;DT(-0.5,1.5,0)rec[-12]_rec[-4];DT(0.5,-0.5,0)rec[-16]_rec[-8];DT(0.5,0.5,0)rec[-11]_rec[-3];DT(0.5,1.5,0)rec[-15]_rec[-7];DT(1.5,0.5,0)rec[-14]_rec[-6];DT(1.5,1.5,0)rec[-10]_rec[-2];DT(1.5,2.5,0)rec[-13]_rec[-5];DT(2.5,0.5,0)rec[-9]_rec[-1];SHIFT_COORDS(0,0,1);TICK;};R_10_12_13_14_16_9_11_15_17_18;TICK;H_0_2_4_9_10_11_12_13_14_15_16_17_18;TICK;CZ_0_10_1_11_2_12_4_14_5_15_7_17;TICK;H_0_1_2_3_4_5_7;TICK;CZ_0_11_3_10_4_15_5_12_6_17_7_14;TICK;H_3_6_7_10_14_17;SQRT_X_0_4_8;TICK;CZ_1_12_2_9_3_14_4_11_5_16_6_13_7_18_8_15;TICK;C_XYZ_11_14_15_18;C_ZYX_4_8;H_1_3_6_7;TICK;CZ_1_9_3_13_4_12_7_17_8_16;TICK;CZ_4_14_8_18;TICK;H_9_12_13_16;SQRT_X_14_18;TICK;M_12_14_16_17_18_0_9_10_11_13_15;DT(-0.5,1.5,0)rec[-15]_rec[-5];DT(0.5,-0.5,0)rec[-19]_rec[-4];DT(0.5,0.5,0)rec[-14]_rec[-10]_rec[-3];DT(0.5,1.5,0)rec[-18]_rec[-11];DT(1.5,0.5,0)rec[-17]_rec[-2];DT(1.5,1.5,0)rec[-13]_rec[-7]_rec[-1];DT(1.5,2.5,0)rec[-16]_rec[-9];DT(2.5,0.5,0)rec[-12]_rec[-8];OI(0)rec[-11]_rec[-10]_rec[-9]_rec[-8]_rec[-7]_rec[-6];SHIFT_COORDS(0,0,1);TICK;R_12_14_16_18_9_11_13_15;TICK;H_9_11_12_13_14_15_16_17_18;SQRT_X_0;TICK;CZ_1_9_3_11_4_12_6_14_7_15_8_16;TICK;H_1_3_4_6_7_8;TICK;CZ_1_12_2_9_3_14_4_11_5_16_6_13_7_18_8_15;TICK;CZ_4_15_5_12_7_14;TICK;H_1_2_3_4_5_7_8_9;TICK;CZ_1_11_2_12_3_13_4_14_5_15_8_18;TICK;H_2_5_11_12_13_14_15_16_18;TICK;M_12_14_16_18_9_11_13_15;DT(-0.5,1.5,0)rec[-13]_rec[-4];DT(0.5,0.5,0)rec[-18]_rec[-14]_rec[-12]_rec[-11]_rec[-3];DT(0.5,1.5,0)rec[-19]_rec[-8];DT(1.5,-0.5,0)rec[-10]_rec[-2];DT(1.5,0.5,0)rec[-18]_rec[-7];DT(1.5,1.5,0)rec[-18]_rec[-15]_rec[-9]_rec[-1];DT(1.5,2.5,0)rec[-17]_rec[-6];DT(2.5,1.5,0)rec[-16]_rec[-15]_rec[-5];SHIFT_COORDS(0,0,1);TICK;R_12_14_16_18_9_11_13_15;TICK;H_6_9_11_12_13_14_15_16_18;TICK;CZ_1_9_3_11_4_12_6_14_7_15_8_16;TICK;H_1_3_4_6_7_8;TICK;CZ_1_12_2_9_3_14_4_11_5_16_6_13_7_18_8_15;TICK;CZ_4_15_5_12_7_14;TICK;H_1_2_3_4_5_8_9;TICK;CZ_1_11_2_12_3_13_4_14_5_15_8_18;TICK;H_2_4_5_11_12_13_14_15_16_18;TICK;M_12_14_16_18_5_7_8_1_2_3_4_6_9_11_13_15;DT(-0.5,1.5,0)rec[-20]_rec[-4];DT(0.5,0.5,0)rec[-19]_rec[-3];DT(0.5,1.5,0)rec[-24]_rec[-16];DT(1.5,-0.5,0)rec[-18]_rec[-2];DT(1.5,0.5,0)rec[-23]_rec[-15];DT(1.5,1.5,0)rec[-17]_rec[-1];DT(1.5,2.5,0)rec[-22]_rec[-14];DT(2.5,1.5,0)rec[-21]_rec[-13];DT(-0.5,1.5,0)rec[-9]_rec[-8]_rec[-4];DT(0.5,0.5,0)rec[-9]_rec[-7]_rec[-6]_rec[-3];DT(1.5,-0.5,0)rec[-7]_rec[-5]_rec[-2];DT(1.5,2.5,0)rec[-14]_rec[-12]_rec[-10];DT(2.5,1.5,0)rec[-13]_rec[-11]_rec[-10];SHIFT_COORDS(0,0,1)_
.. _xcz: https://algassert.com/crumble#circuit=Q(-1,1)0;Q(-1,3)1;Q(-1,5)2;Q(0,0)3;Q(0,2)4;Q(0,4)5;Q(0,6)6;Q(1,-1)7;Q(1,1)8;Q(1,3)9;Q(1,5)10;Q(2,0)11;Q(2,2)12;Q(2,4)13;Q(2,6)14;Q(3,-1)15;Q(3,1)16;Q(3,3)17;Q(3,5)18;Q(3,7)19;Q(4,0)20;Q(4,2)21;Q(4,4)22;Q(4,6)23;Q(5,-1)24;Q(5,1)25;Q(5,3)26;Q(5,5)27;Q(5,7)28;Q(6,0)29;Q(6,2)30;Q(6,4)31;Q(6,6)32;Q(7,1)33;Q(7,3)34;R_12_16_20_22_25_26_30_4_8_9_13_17_18_21_23_27;TICK;H_4_12_13_17_20_21_22_23_26_27_30;TICK;CZ_4_9_12_17_13_18_20_25_21_26_22_27;TICK;H_9_17_18_25_26_27;TICK;CZ_12_16_17_21_22_26;TICK;CZ_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;H_4_8_9_16_17_18_20_25_26_27;TICK;CZ_8_12_9_13_16_21_17_22_18_23_25_30;TICK;H_8_12_13_16_21_22_23_30;TICK;M_12_20_22_30_4_13_21_23;DT(4,0,0)rec[-7];DT(0,2,0)rec[-4];DT(4,6,0)rec[-1];DT(2,4,0)rec[-3];DT(6,2,0)rec[-5];SHIFT_COORDS(0,0,1);TICK;R_12_20_22_30_4_13_21_23;TICK;H_4_12_13_20_21_22_23_30;TICK;CZ_4_9_12_17_13_18_20_25_21_26_22_27;TICK;H_9_17_18_25_26_27;TICK;CZ_12_16_17_21_22_26;TICK;CZ_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;H_4_8_9_16_17_18_20_25;TICK;CZ_8_12_9_13_16_21_17_22_18_23_25_30;TICK;H_8_12_13_21_22_23_30;TICK;M_12_20_22_30_4_13_21_23;DT(2,2,0)rec[-16]_rec[-8];DT(4,2,0)rec[-10]_rec[-2];DT(0,2,0)rec[-12]_rec[-4];DT(4,0,0)rec[-15]_rec[-7];DT(6,2,0)rec[-13]_rec[-5];DT(2,4,0)rec[-11]_rec[-3];DT(4,4,0)rec[-14]_rec[-6];DT(4,6,0)rec[-9]_rec[-1];SHIFT_COORDS(0,0,1);TICK;R_11_12_20_22_30_4_5_13_21_23_10;TICK;C_XYZ_12_20;C_ZYX_10_13_21;H_4_5_22_23_30;TICK;CZ_12_17_20_25;TICK;CZ_4_9_11_16_17_22_18_23_25_30;TICK;H_9_11_16_18;SQRT_X_12_17_20_25;TICK;CZ_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;C_ZYX_17;H_4_8_9_12_16_18_20_23_27_30;SQRT_X_25;TICK;CZ_5_9_8_11_10_13_12_16_17_21_22_26;TICK;H_8_9_10_16_17_26;TICK;CZ_5_10_11_16_12_17_13_18_21_26_22_27;TICK;H_5_10_11_12_13_21_22_26_27;TICK;M_11_13_20_21_23_4_5_12_22_30;DT(6,2,0)rec[-15]_rec[-1];DT(0,2,0)rec[-14]_rec[-5];DT(4,0,0)rec[-17]_rec[-8];DT(4,4,0)rec[-16]_rec[-2];DT(4,6,0)rec[-11]_rec[-6];DT(1,4,0)rec[-13]_rec[-9]_rec[-4];DT(2,0,0)rec[-18]_rec[-10];DT(3,2,0)rec[-12]_rec[-7]_rec[-3];SHIFT_COORDS(0,0,1);TICK;R_5_11_12_13_21_22_23_30;TICK;H_5_11_12_13_21_22_23_30;TICK;CZ_8_12_9_13_16_21_17_22_18_23_25_30;TICK;H_8_9_16_17_18_25;TICK;CZ_5_9_13_17_21_25_23_27;TICK;CZ_8_11_9_12_10_13_17_21_18_22_26_30;TICK;CZ_12_16_22_26;TICK;H_8_10_16_17_18_25_26_27;TICK;CZ_5_10_11_16_12_17_13_18_21_26_22_27;TICK;H_5_10_11_12_13_21_22_23_26_27_30;TICK;M_5_11_12_13_21_22_23_30;DT(6,2,0)rec[-9]_rec[-1];DT(2,0,0)rec[-18]_rec[-7];DT(0,4,0)rec[-12]_rec[-8];DT(4,2,0)rec[-16]_rec[-15]_rec[-4];DT(2,4,0)rec[-17]_rec[-5];DT(2,2,0)rec[-13]_rec[-11]_rec[-6];DT(4,4,0)rec[-10]_rec[-3];DT(4,6,0)rec[-14]_rec[-2];SHIFT_COORDS(0,0,1);TICK;R_5_11_12_13_21_22_23_30;TICK;H_5_9_11_12_13_21_22_23_30;TICK;CZ_8_12_9_13_16_21_17_22_18_23_25_30;TICK;H_8_9_16_17_18_25;TICK;CZ_5_9_13_17_21_25_23_27;TICK;CZ_8_11_9_12_10_13_17_21_18_22_26_30;TICK;CZ_12_16_22_26;TICK;H_8_10_16_17_18_25_26_27;TICK;CZ_5_10_11_16_12_17_13_18_21_26_22_27;TICK;H_5_10_11_12_13_21_22_23_26_27_30;TICK;M_5_11_12_13_21_22_23_30;DT(4,2,0)rec[-12]_rec[-4];DT(6,2,0)rec[-9]_rec[-1];DT(2,2,0)rec[-14]_rec[-6];DT(2,0,0)rec[-15]_rec[-7];DT(0,4,0)rec[-16]_rec[-8];DT(2,4,0)rec[-13]_rec[-5];DT(4,4,0)rec[-11]_rec[-3];DT(4,6,0)rec[-10]_rec[-2];SHIFT_COORDS(0,0,1);TICK;R_5_11_12_13_21_22_23_30;TICK;H_5_9_11_12_13_21_22_23_30;TICK;CZ_8_12_9_13_16_21_17_22_18_23_25_30;TICK;H_8_9_16_17_18_25;TICK;CZ_5_9_13_17_21_25_23_27;TICK;CZ_8_11_9_12_10_13_17_21_18_22_26_30;TICK;CZ_12_16_22_26;TICK;C_XYZ_25;H_10_16_17_18_26_27;TICK;CZ_5_10_11_16_12_17_13_18_21_26_22_27;TICK;H_5_11_12_13_21_22_23_30;TICK;M_5_11_12_13_21_22_23_30;DT(4,2,0)rec[-12]_rec[-4];DT(6,2,0)rec[-9]_rec[-1];DT(2,2,0)rec[-14]_rec[-6];DT(2,0,0)rec[-15]_rec[-7];DT(0,4,0)rec[-16]_rec[-8];DT(2,4,0)rec[-13]_rec[-5];DT(4,4,0)rec[-11]_rec[-3];DT(4,6,0)rec[-10]_rec[-2];SHIFT_COORDS(0,0,1);TICK;R_11_13_20_21_23_4_5_12_22_30;TICK;H_4_5_11_12_13_20_21_22_23_30;TICK;CZ_5_10_11_16_12_17_13_18_21_26_22_27;TICK;H_10_16_17_18_26_27;TICK;CZ_5_9_8_11_10_13_12_16_17_21_22_26;TICK;C_XYZ_10_17;H_5_8_9_11_12_16;TICK;CZ_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;C_XYZ_13_21;H_8_9_16_18;SQRT_X_12_17_20_25;TICK;CZ_4_9_11_16_17_22_18_23_25_30;TICK;CZ_12_17_20_25;TICK;C_ZYX_12_20;H_4_22_23_30;TICK;M_11_12_20_22_30_4_5_13_21_23_10;DT(0,2,0)rec[-17]_rec[-6];DT(6,2,0)rec[-12]_rec[-7];DT(2,0,0)rec[-18]_rec[-11];DT(0,4,0)rec[-19]_rec[-5];DT(4,1,0)rec[-15]_rec[-9]_rec[-3];DT(4,4,0)rec[-14]_rec[-8];DT(4,6,0)rec[-13]_rec[-2];DT(2,3,0)rec[-16]_rec[-10]_rec[-4];OI(0)rec[-9]_rec[-7]_rec[-5]_rec[-4]_rec[-1];SHIFT_COORDS(0,0,1);TICK;R_12_20_22_30_4_13_21_23;TICK;H_4_5_12_13_20_21_22_23_30;SQRT_X_10;TICK;CZ_8_12_9_13_16_21_17_22_18_23_25_30;TICK;H_8_9_16_17_18_25;TICK;CZ_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;CZ_12_16_17_21_22_26;TICK;H_8_9_16_17_18_25_26_27_30;TICK;CZ_4_9_12_17_13_18_20_25_21_26_22_27;TICK;H_4_12_13_20_21_22_23_26_27;TICK;M_12_20_22_30_4_13_21_23;DT(4,2,0)rec[-18]_rec[-17]_rec[-11]_rec[-2];DT(6,2,0)rec[-15]_rec[-5];DT(2,2,0)rec[-18]_rec[-8];DT(0,2,0)rec[-14]_rec[-4];DT(4,0,0)rec[-19]_rec[-17]_rec[-7];DT(4,4,0)rec[-16]_rec[-6];DT(4,6,0)rec[-10]_rec[-1];DT(2,4,0)rec[-18]_rec[-13]_rec[-12]_rec[-9]_rec[-3];SHIFT_COORDS(0,0,1);TICK;R_12_20_22_30_4_13_21_23;TICK;H_4_12_13_20_21_22_23_30;TICK;CZ_8_12_9_13_16_21_17_22_18_23_25_30;TICK;H_8_9_16_17_18_25;TICK;CZ_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;CZ_12_16_17_21_22_26;TICK;H_9_17_18_25_26_27_30;TICK;CZ_4_9_12_17_13_18_20_25_21_26_22_27;TICK;H_4_12_13_17_20_21_22_23_26_27;TICK;M_12_16_20_22_25_26_30_4_8_9_13_17_18_21_23_27;DT(4,6,0)rec[-4]_rec[-2]_rec[-1];DT(2,2,0)rec[-24]_rec[-16];DT(0,2,0)rec[-20]_rec[-9];DT(4,0,0)rec[-23]_rec[-14];DT(4,2,0)rec[-18]_rec[-3];DT(6,2,0)rec[-21]_rec[-10];DT(2,4,0)rec[-19]_rec[-6];DT(4,4,0)rec[-22]_rec[-13];DT(4,6,0)rec[-17]_rec[-2];DT(0,2,0)rec[-9]_rec[-8]_rec[-7];DT(2,4,0)rec[-7]_rec[-6]_rec[-5]_rec[-4];DT(4,0,0)rec[-15]_rec[-14]_rec[-12];DT(6,2,0)rec[-12]_rec[-11]_rec[-10];SHIFT_COORDS(0,0,1)_
.. _zcz: https://algassert.com/crumble#circuit=Q(-1,1)0;Q(-1,3)1;Q(-1,5)2;Q(0,0)3;Q(0,2)4;Q(0,4)5;Q(0,6)6;Q(1,-1)7;Q(1,1)8;Q(1,3)9;Q(1,5)10;Q(1,7)11;Q(2,0)12;Q(2,2)13;Q(2,4)14;Q(2,6)15;Q(3,-1)16;Q(3,1)17;Q(3,3)18;Q(3,5)19;Q(3,7)20;Q(4,0)21;Q(4,2)22;Q(4,4)23;Q(4,6)24;Q(5,-1)25;Q(5,1)26;Q(5,3)27;Q(5,5)28;Q(6,0)29;Q(6,2)30;Q(6,4)31;Q(6,6)32;Q(7,3)33;Q(7,5)34;R_8_12_14_17_18_22_27_28_31_5_9_10_13_15_19_23;TICK;H_5_12_13_14_15_18_19_22_23_28_31;TICK;CZ_5_10_12_17_13_18_14_19_22_27_23_28;TICK;H_10_17_18_19_27_28;TICK;CZ_9_13_14_18_19_23;TICK;CZ_5_9_8_12_10_14_13_17_15_19_18_22_23_27_28_31;TICK;H_5_8_9_10_12_17_18_19_27_28;TICK;CZ_8_13_9_14_10_15_17_22_18_23_27_31;TICK;H_8_9_13_14_15_22_23_31;TICK;M_12_14_22_31_5_13_15_23;DT(6,4,0)rec[-5];DT(2,6,0)rec[-2];DT(0,4,0)rec[-4];DT(4,2,0)rec[-6];DT(2,0,0)rec[-8];SHIFT_COORDS(0,0,1);TICK;R_12_14_22_31_5_13_15_23;TICK;H_5_12_13_14_15_22_23_31;TICK;CZ_5_10_12_17_13_18_14_19_22_27_23_28;TICK;H_10_17_18_19_27_28;TICK;CZ_9_13_14_18_19_23;TICK;CZ_5_9_8_12_10_14_13_17_15_19_18_22_23_27_28_31;TICK;H_5_8_9_10_12_17_18_27;TICK;CZ_8_13_9_14_10_15_17_22_18_23_27_31;TICK;H_8_13_14_15_22_23_31;TICK;M_12_14_22_31_5_13_15_23;DT(4,2,0)rec[-14]_rec[-6];DT(0,4,0)rec[-12]_rec[-4];DT(2,2,0)rec[-11]_rec[-3];DT(2,0,0)rec[-16]_rec[-8];DT(2,4,0)rec[-15]_rec[-7];DT(4,4,0)rec[-9]_rec[-1];DT(6,4,0)rec[-13]_rec[-5];DT(2,6,0)rec[-10]_rec[-2];SHIFT_COORDS(0,0,1);TICK;R_12_14_21_22_31_26_4_5_13_15_23;TICK;C_XYZ_5_13;C_ZYX_14_22_26;H_12_15_21_23_31;TICK;CZ_5_10_13_18;TICK;CZ_4_9_10_15_12_17_18_23_27_31;TICK;H_4_9_17_27;SQRT_X_5_10_13_18;TICK;CZ_5_9_8_12_10_14_13_17_15_19_18_22_23_27_28_31;TICK;C_ZYX_18;H_5_8_9_12_13_15_17_27_28_31;SQRT_X_10;TICK;CZ_4_8_9_13_14_18_17_21_19_23_22_26;TICK;H_8_9_17_18_19_26;TICK;CZ_4_9_13_18_14_19_21_26_22_27_23_28;TICK;H_4_13_14_19_21_22_23_26_28;TICK;M_12_13_15_21_23_4_5_14_22_31;DT(0,2,0)rec[-13]_rec[-5];DT(0,4,0)rec[-14]_rec[-4];DT(2,0,0)rec[-18]_rec[-10];DT(4,4,0)rec[-11]_rec[-6];DT(4,1,0)rec[-16]_rec[-7]_rec[-2];DT(6,4,0)rec[-15]_rec[-1];DT(2,6,0)rec[-12]_rec[-8];DT(2,3,0)rec[-17]_rec[-9]_rec[-3];SHIFT_COORDS(0,0,1);TICK;R_4_13_14_15_21_22_23_31;TICK;H_4_13_14_15_21_22_23_31;TICK;CZ_8_13_9_14_10_15_17_22_18_23_27_31;TICK;H_8_9_10_17_18_27;TICK;CZ_4_8_13_17_15_19_23_27;TICK;CZ_9_13_10_14_17_21_18_22_19_23_28_31;TICK;CZ_14_18_22_26;TICK;H_8_9_10_18_19_26_27_28;TICK;CZ_4_9_13_18_14_19_21_26_22_27_23_28;TICK;H_4_13_14_15_19_21_22_23_26_28_31;TICK;M_4_13_14_15_21_22_23_31;DT(4,2,0)rec[-10]_rec[-3];DT(0,2,0)rec[-13]_rec[-8];DT(4,0,0)rec[-15]_rec[-4];DT(2,2,0)rec[-18]_rec[-17]_rec[-7];DT(4,4,0)rec[-14]_rec[-2];DT(6,4,0)rec[-9]_rec[-1];DT(2,4,0)rec[-12]_rec[-11]_rec[-6];DT(2,6,0)rec[-16]_rec[-5];SHIFT_COORDS(0,0,1);TICK;R_4_13_14_15_21_22_23_31;TICK;H_4_13_14_15_17_21_22_23_31;TICK;CZ_8_13_9_14_10_15_17_22_18_23_27_31;TICK;H_8_9_10_17_18_27;TICK;CZ_4_8_13_17_15_19_23_27;TICK;CZ_9_13_10_14_17_21_18_22_19_23_28_31;TICK;CZ_14_18_22_26;TICK;H_8_9_10_18_19_26_27_28;TICK;CZ_4_9_13_18_14_19_21_26_22_27_23_28;TICK;H_4_13_14_15_19_21_22_23_26_28_31;TICK;M_4_13_14_15_21_22_23_31;DT(2,2,0)rec[-15]_rec[-7];DT(4,2,0)rec[-11]_rec[-3];DT(0,2,0)rec[-16]_rec[-8];DT(4,0,0)rec[-12]_rec[-4];DT(2,4,0)rec[-14]_rec[-6];DT(4,4,0)rec[-10]_rec[-2];DT(6,4,0)rec[-9]_rec[-1];DT(2,6,0)rec[-13]_rec[-5];SHIFT_COORDS(0,0,1);TICK;R_4_13_14_15_21_22_23_31;TICK;H_4_13_14_15_17_21_22_23_31;TICK;CZ_8_13_9_14_10_15_17_22_18_23_27_31;TICK;H_8_9_10_17_18_27;TICK;CZ_4_8_13_17_15_19_23_27;TICK;CZ_9_13_10_14_17_21_18_22_19_23_28_31;TICK;CZ_14_18_22_26;TICK;C_XYZ_10;H_9_18_19_26_27_28;TICK;CZ_4_9_13_18_14_19_21_26_22_27_23_28;TICK;H_4_13_14_15_21_22_23_31;TICK;M_4_13_14_15_21_22_23_31;DT(2,2,0)rec[-15]_rec[-7];DT(4,2,0)rec[-11]_rec[-3];DT(0,2,0)rec[-16]_rec[-8];DT(4,0,0)rec[-12]_rec[-4];DT(2,4,0)rec[-14]_rec[-6];DT(4,4,0)rec[-10]_rec[-2];DT(6,4,0)rec[-9]_rec[-1];DT(2,6,0)rec[-13]_rec[-5];SHIFT_COORDS(0,0,1);TICK;R_12_13_15_21_23_4_5_14_22_31;TICK;H_4_5_12_13_14_15_21_22_23_31;TICK;CZ_4_9_13_18_14_19_21_26_22_27_23_28;TICK;H_9_18_19_26_27_28;TICK;CZ_4_8_9_13_14_18_17_21_19_23_22_26;TICK;C_XYZ_18_26;H_4_8_9_13_17_21;TICK;CZ_5_9_8_12_10_14_13_17_15_19_18_22_23_27_28_31;TICK;C_XYZ_14_22;H_8_9_17_27;SQRT_X_5_10_13_18;TICK;CZ_4_9_10_15_12_17_18_23_27_31;TICK;CZ_5_10_13_18;TICK;C_ZYX_5_13;H_12_15_23_31;TICK;M_12_14_21_22_31_26_4_5_13_15_23;DT(0,2,0)rec[-19]_rec[-5];DT(4,0,0)rec[-15]_rec[-9];DT(4,4,0)rec[-13]_rec[-1];DT(6,4,0)rec[-12]_rec[-7];DT(2,6,0)rec[-16]_rec[-2];DT(1,4,0)rec[-17]_rec[-10]_rec[-4];DT(2,0,0)rec[-18]_rec[-11];DT(3,2,0)rec[-14]_rec[-8]_rec[-3];OI(0)rec[-9]_rec[-8]_rec[-6]_rec[-4]_rec[-2];SHIFT_COORDS(0,0,1);TICK;R_12_14_22_31_5_13_15_23;TICK;H_5_12_13_14_15_21_22_23_31;SQRT_X_26;TICK;CZ_8_13_9_14_10_15_17_22_18_23_27_31;TICK;H_8_9_10_17_18_27;TICK;CZ_5_9_8_12_10_14_13_17_15_19_18_22_23_27_28_31;TICK;CZ_9_13_14_18_19_23;TICK;H_8_9_10_15_17_18_19_27_28;TICK;CZ_5_10_12_17_13_18_14_19_22_27_23_28;TICK;H_5_12_13_14_19_22_23_28_31;TICK;M_12_14_22_31_5_13_15_23;DT(2,2,0)rec[-11]_rec[-3];DT(2,0,0)rec[-19]_rec[-8];DT(2,4,0)rec[-18]_rec[-12]_rec[-11]_rec[-7];DT(4,4,0)rec[-9]_rec[-1];DT(6,4,0)rec[-15]_rec[-5];DT(0,4,0)rec[-13]_rec[-12]_rec[-4];DT(2,6,0)rec[-10]_rec[-2];DT(4,2,0)rec[-17]_rec[-16]_rec[-14]_rec[-11]_rec[-6];SHIFT_COORDS(0,0,1);TICK;R_12_14_22_31_5_13_15_23;TICK;H_5_12_13_14_15_22_23_31;TICK;CZ_8_13_9_14_10_15_17_22_18_23_27_31;TICK;H_8_9_10_17_18_27;TICK;CZ_5_9_8_12_10_14_13_17_15_19_18_22_23_27_28_31;TICK;CZ_9_13_14_18_19_23;TICK;H_10_15_17_18_19_27_28;TICK;CZ_5_10_12_17_13_18_14_19_22_27_23_28;TICK;H_5_12_13_14_18_19_22_23_28_31;TICK;M_8_12_14_17_18_22_27_28_31_5_9_10_13_15_19_23;DT(2,6,0)rec[-5]_rec[-3]_rec[-2];DT(6,4,0)rec[-10]_rec[-9]_rec[-8];DT(4,2,0)rec[-22]_rec[-11];DT(2,2,0)rec[-19]_rec[-4];DT(2,0,0)rec[-24]_rec[-15];DT(0,4,0)rec[-20]_rec[-7];DT(2,4,0)rec[-23]_rec[-14];DT(2,0,0)rec[-16]_rec[-15]_rec[-13];DT(4,4,0)rec[-17]_rec[-1];DT(6,4,0)rec[-21]_rec[-8];DT(2,6,0)rec[-18]_rec[-3];DT(0,4,0)rec[-7]_rec[-6]_rec[-5];DT(4,2,0)rec[-13]_rec[-12]_rec[-11]_rec[-10];SHIFT_COORDS(0,0,1)_
.. _gna: https://algassert.com/crumble#circuit=Q(0,0)0;Q(0,1)1;Q(0,2)2;Q(1,0)3;Q(1,1)4;Q(1,2)5;Q(2,0)6;Q(2,1)7;Q(2,2)8;Q(-0.5,1.5)9;Q(0.5,-0.5)10;Q(0.5,0.5)11;Q(0.5,1.5)12;Q(1.5,-0.5)13;Q(1.5,0.5)14;Q(1.5,1.5)15;Q(1.5,2.5)16;Q(2.5,0.5)17;Q(2.5,1.5)18;R_15_13_11_9_6_4_3_2_1;RX_8_7_5_18_16_14_12;TICK;CX_18_8_14_4_12_2_5_15_3_13_1_11;TICK;CX_14_7_12_5_4_15;TICK;CX_18_7_16_5_14_3_12_1_8_15_6_13_4_11_2_9;TICK;CX_16_8_14_6_12_4_7_15_3_11_1_9;TICK;M_15_13_11_9;MX_18_16_14_12;DT(-0.5,1.5,0)rec[-5];DT(0.5,0.5,0)rec[-6];DT(1.5,-0.5,0)rec[-7];DT(1.5,2.5,0)rec[-3];DT(2.5,1.5,0)rec[-4];SHIFT_COORDS(0,0,1);TICK;R_15_13_11_9;RX_18_16_14_12;TICK;CX_18_8_14_4_12_2_5_15_3_13_1_11;TICK;CX_14_7_12_5_4_15;TICK;CX_18_7_16_5_14_3_12_1_8_15_6_13_4_11_2_9;TICK;CX_16_8_14_6_12_4_7_15_3_11_1_9;TICK;M_15_13_11_9;MX_18_16_14_12;DT(-0.5,1.5,0)rec[-13]_rec[-5];DT(0.5,0.5,0)rec[-14]_rec[-6];DT(0.5,1.5,0)rec[-9]_rec[-1];DT(1.5,-0.5,0)rec[-15]_rec[-7];DT(1.5,0.5,0)rec[-10]_rec[-2];DT(1.5,1.5,0)rec[-16]_rec[-8];DT(1.5,2.5,0)rec[-11]_rec[-3];DT(2.5,1.5,0)rec[-12]_rec[-4];SHIFT_COORDS(0,0,1);TICK;R_15_13_11_10_9;RY_0;RX_18_17_16_14_12;TICK;SQRT_X_15_11;H_18_17_14_13_10_7_6_3;TICK;XCY_8_18_4_14;TICK;CX_1_9_16_8_12_4_17_7_13_3;TICK;CX_2_9_16_5_12_1;XCY_15_8_11_4;CX_13_6_7_18_3_14;TICK;CX_6_17_4_15_0_11_14_7_12_5_10_3;TICK;CX_7_17_5_15_1_11_14_4_12_2_10_0;TICK;M_18_17_15_11_9;MX_16_14_13_12_10;DT(-0.5,1.5,0)rec[-15]_rec[-6];DT(0.5,0.5,0)rec[-16]_rec[-7]_rec[-1];DT(0.5,1.5,0)rec[-11]_rec[-2];DT(1.5,-0.5,0)rec[-17]_rec[-3];DT(1.5,0.5,0)rec[-12]_rec[-9];DT(1.5,1.5,0)rec[-18]_rec[-8]_rec[-4];DT(1.5,2.5,0)rec[-13]_rec[-5];DT(2.5,1.5,0)rec[-14]_rec[-10];OI(0)rec[-10]_rec[-9]_rec[-5]_rec[-2];SHIFT_COORDS(0,0,1);TICK;RX_10_12_14_16;R_9_11_15_17;TICK;CX_1_9_3_11_7_15_12_4_14_6_16_8;TICK;CX_2_9_4_11_8_15_12_1_14_3_16_5;TICK;CX_0_11_4_15_6_17_10_3_12_5_14_7;TICK;CX_1_11_5_15_7_17_10_0_12_2_14_4;TICK;MX_10_12_14_16;M_9_11_15_17;DT(-0.5,1.5,0)rec[-14]_rec[-4];DT(0.5,-0.5,0)rec[-9]_rec[-8];DT(0.5,0.5,0)rec[-15]_rec[-3];DT(0.5,1.5,0)rec[-10]_rec[-7];DT(1.5,0.5,0)rec[-12]_rec[-11]_rec[-6];DT(1.5,1.5,0)rec[-18]_rec[-16]_rec[-2];DT(1.5,2.5,0)rec[-13]_rec[-5];DT(2.5,0.5,0)rec[-17]_rec[-1];SHIFT_COORDS(0,0,1);TICK;REPEAT_2_{;RX_10_12_14_16;R_9_11_15_17;TICK;CX_1_9_3_11_7_15_12_4_14_6_16_8;TICK;CX_2_9_4_11_8_15_12_1_14_3_16_5;TICK;CX_0_11_4_15_6_17_10_3_12_5_14_7;TICK;CX_1_11_5_15_7_17_10_0_12_2_14_4;TICK;MX_10_12_14_16;M_9_11_15_17;DT(-0.5,1.5,0)rec[-12]_rec[-4];DT(0.5,-0.5,0)rec[-16]_rec[-8];DT(0.5,0.5,0)rec[-11]_rec[-3];DT(0.5,1.5,0)rec[-15]_rec[-7];DT(1.5,0.5,0)rec[-14]_rec[-6];DT(1.5,1.5,0)rec[-10]_rec[-2];DT(1.5,2.5,0)rec[-13]_rec[-5];DT(2.5,0.5,0)rec[-9]_rec[-1];SHIFT_COORDS(0,0,1);TICK;};RX_10_12_13_14_16;R_9_11_15_17_18;TICK;CX_10_0_12_2_14_4_1_11_5_15_7_17;TICK;CX_10_3_12_5_14_7_0_11_4_15_6_17;TICK;CX_3_14_7_18_13_6;XCY_11_4_15_8;CX_12_1_16_5_2_9;TICK;CX_13_3_17_7_12_4_16_8_1_9;TICK;XCY_4_14_8_18;TICK;H_3_6_7_10_13_14_17_18;SQRT_X_11_15;TICK;MX_12_14_16_17_18;MY_0;M_9_10_11_13_15;DT(-0.5,1.5,0)rec[-15]_rec[-5];DT(0.5,-0.5,0)rec[-19]_rec[-4];DT(0.5,0.5,0)rec[-14]_rec[-10]_rec[-3];DT(0.5,1.5,0)rec[-18]_rec[-11];DT(1.5,0.5,0)rec[-17]_rec[-2];DT(1.5,1.5,0)rec[-13]_rec[-7]_rec[-1];DT(1.5,2.5,0)rec[-16]_rec[-9];DT(2.5,0.5,0)rec[-12]_rec[-8];OI(0)rec[-11]_rec[-10]_rec[-9]_rec[-8]_rec[-7]_rec[-6];SHIFT_COORDS(0,0,1);TICK;RX_12_14_16_18;R_9_11_13_15;TICK;CX_1_9_3_11_7_15_12_4_14_6_16_8;TICK;CX_2_9_4_11_6_13_8_15_12_1_14_3_16_5_18_7;TICK;CX_4_15_12_5_14_7;TICK;CX_1_11_3_13_5_15_12_2_14_4_18_8;TICK;MX_12_14_16_18;M_9_11_13_15;DT(-0.5,1.5,0)rec[-13]_rec[-4];DT(0.5,0.5,0)rec[-18]_rec[-14]_rec[-12]_rec[-11]_rec[-3];DT(0.5,1.5,0)rec[-19]_rec[-8];DT(1.5,-0.5,0)rec[-10]_rec[-2];DT(1.5,0.5,0)rec[-18]_rec[-7];DT(1.5,1.5,0)rec[-18]_rec[-15]_rec[-9]_rec[-1];DT(1.5,2.5,0)rec[-17]_rec[-6];DT(2.5,1.5,0)rec[-16]_rec[-15]_rec[-5];SHIFT_COORDS(0,0,1);TICK;RX_12_14_16_18;R_9_11_13_15;TICK;CX_1_9_3_11_7_15_12_4_14_6_16_8;TICK;CX_2_9_4_11_6_13_8_15_12_1_14_3_16_5_18_7;TICK;CX_4_15_12_5_14_7;TICK;CX_1_11_3_13_5_15_12_2_14_4_18_8;TICK;MX_12_14_16_18_5_7_8;M_1_2_3_4_6_9_11_13_15;DT(-0.5,1.5,0)rec[-20]_rec[-4];DT(0.5,0.5,0)rec[-19]_rec[-3];DT(0.5,1.5,0)rec[-24]_rec[-16];DT(1.5,-0.5,0)rec[-18]_rec[-2];DT(1.5,0.5,0)rec[-23]_rec[-15];DT(1.5,1.5,0)rec[-17]_rec[-1];DT(1.5,2.5,0)rec[-22]_rec[-14];DT(2.5,1.5,0)rec[-21]_rec[-13];DT(-0.5,1.5,0)rec[-9]_rec[-8]_rec[-4];DT(0.5,0.5,0)rec[-9]_rec[-7]_rec[-6]_rec[-3];DT(1.5,-0.5,0)rec[-7]_rec[-5]_rec[-2];DT(1.5,2.5,0)rec[-14]_rec[-12]_rec[-10];DT(2.5,1.5,0)rec[-13]_rec[-11]_rec[-10];SHIFT_COORDS(0,0,1);TICK_
.. _xna: https://algassert.com/crumble#circuit=Q(-1,1)0;Q(-1,3)1;Q(-1,5)2;Q(0,0)3;Q(0,2)4;Q(0,4)5;Q(0,6)6;Q(1,-1)7;Q(1,1)8;Q(1,3)9;Q(1,5)10;Q(2,0)11;Q(2,2)12;Q(2,4)13;Q(2,6)14;Q(3,-1)15;Q(3,1)16;Q(3,3)17;Q(3,5)18;Q(3,7)19;Q(4,0)20;Q(4,2)21;Q(4,4)22;Q(4,6)23;Q(5,-1)24;Q(5,1)25;Q(5,3)26;Q(5,5)27;Q(5,7)28;Q(6,0)29;Q(6,2)30;Q(6,4)31;Q(6,6)32;Q(7,1)33;Q(7,3)34;R_12_16_20_22_25_26_30;RX_4_8_9_13_17_18_21_23_27;TICK;CX_4_9_13_18_17_12_21_26_25_20_27_22;TICK;CX_16_12_21_17_26_22;TICK;CX_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;CX_8_12_13_9_17_22_21_16_23_18_25_30;TICK;M_12_20_22_30;MX_4_13_21_23;DT(4,0,0)rec[-7];DT(0,2,0)rec[-4];DT(4,6,0)rec[-1];DT(2,4,0)rec[-3];DT(6,2,0)rec[-5];SHIFT_COORDS(0,0,1);TICK;R_12_20_22_30;RX_4_13_21_23;TICK;CX_4_9_13_18_17_12_21_26_25_20_27_22;TICK;CX_16_12_21_17_26_22;TICK;CX_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;CX_8_12_13_9_17_22_21_16_23_18_25_30;TICK;M_12_20_22_30;MX_4_13_21_23;DT(2,2,0)rec[-16]_rec[-8];DT(4,2,0)rec[-10]_rec[-2];DT(0,2,0)rec[-12]_rec[-4];DT(4,0,0)rec[-15]_rec[-7];DT(6,2,0)rec[-13]_rec[-5];DT(2,4,0)rec[-11]_rec[-3];DT(4,4,0)rec[-14]_rec[-6];DT(4,6,0)rec[-9]_rec[-1];SHIFT_COORDS(0,0,1);TICK;R_11_12_20_22_30;RX_4_5_13_21_23;RY_10;TICK;H_4_5_8_9_11_12_16_20;S_DAG_13_21;TICK;CY_17_12_25_20;TICK;CX_9_4_16_11_17_22_23_18_25_30;TICK;CX_8_4_12_9_18_22_20_16_23_27_26_30;CY_13_17_21_25;TICK;CX_9_5_11_8_13_10_16_12_21_17_26_22;TICK;CX_10_5_11_16_13_18_17_12_21_26_27_22;TICK;MX_11_13_20_21_23;M_4_5_12_22_30;DT(6,2,0)rec[-15]_rec[-1];DT(0,2,0)rec[-14]_rec[-5];DT(4,0,0)rec[-17]_rec[-8];DT(4,4,0)rec[-16]_rec[-2];DT(4,6,0)rec[-11]_rec[-6];DT(1,4,0)rec[-13]_rec[-9]_rec[-4];DT(2,0,0)rec[-18]_rec[-10];DT(3,2,0)rec[-12]_rec[-7]_rec[-3];SHIFT_COORDS(0,0,1);TICK;RX_5_11_12_13_21_22_23_30;TICK;CZ_12_8_22_17_30_25;CX_13_9_21_16_23_18;TICK;CX_13_17_21_25_23_27;CZ_5_9;TICK;CX_11_8_13_10_21_17;CZ_12_9_22_18_30_26;TICK;CZ_12_16_22_26;TICK;CX_11_16_13_18_21_26;CZ_5_10_12_17_22_27;TICK;MX_5_11_12_13_21_22_23_30;DT(6,2,0)rec[-9]_rec[-1];DT(2,0,0)rec[-18]_rec[-7];DT(0,4,0)rec[-12]_rec[-8];DT(4,2,0)rec[-16]_rec[-15]_rec[-4];DT(2,4,0)rec[-17]_rec[-5];DT(2,2,0)rec[-13]_rec[-11]_rec[-6];DT(4,4,0)rec[-10]_rec[-3];DT(4,6,0)rec[-14]_rec[-2];SHIFT_COORDS(0,0,1);TICK;RX_5_11_12_13_21_22_23_30;TICK;CZ_12_8_22_17_30_25;CX_13_9_21_16_23_18;TICK;CX_13_17_21_25_23_27;CZ_5_9;TICK;CX_11_8_13_10_21_17;CZ_12_9_22_18_30_26;TICK;CZ_12_16_22_26;TICK;CX_11_16_13_18_21_26;CZ_5_10_12_17_22_27;TICK;MX_5_11_12_13_21_22_23_30;DT(4,2,0)rec[-12]_rec[-4];DT(6,2,0)rec[-9]_rec[-1];DT(2,2,0)rec[-14]_rec[-6];DT(2,0,0)rec[-15]_rec[-7];DT(0,4,0)rec[-16]_rec[-8];DT(2,4,0)rec[-13]_rec[-5];DT(4,4,0)rec[-11]_rec[-3];DT(4,6,0)rec[-10]_rec[-2];SHIFT_COORDS(0,0,1);TICK;RX_5_11_12_13_21_22_23_30;TICK;CZ_12_8_22_17_30_25;CX_13_9_21_16_23_18;TICK;CX_13_17_21_25_23_27;CZ_5_9;TICK;CX_11_8_13_10_21_17;CZ_12_9_22_18_30_26;TICK;CZ_12_16_22_26;TICK;CX_11_16_13_18_21_26;CZ_5_10_12_17_22_27;TICK;MX_5_11_12_13_21_22_23_30;DT(4,2,0)rec[-12]_rec[-4];DT(6,2,0)rec[-9]_rec[-1];DT(2,2,0)rec[-14]_rec[-6];DT(2,0,0)rec[-15]_rec[-7];DT(0,4,0)rec[-16]_rec[-8];DT(2,4,0)rec[-13]_rec[-5];DT(4,4,0)rec[-11]_rec[-3];DT(4,6,0)rec[-10]_rec[-2];SHIFT_COORDS(0,0,1);TICK;RX_11_13_20_21_23;R_4_5_12_22_30;TICK;CX_10_5_11_16_13_18_17_12_21_26_27_22;TICK;CX_9_5_11_8_13_10_16_12_21_17_26_22;TICK;CX_8_4_12_9_18_22_20_16_23_27_26_30;CY_13_17_21_25;TICK;CX_9_4_16_11_17_22_23_18_25_30;TICK;CY_17_12_25_20;TICK;H_4_5_8_9_11_12_16_20;S_13_21;TICK;M_11_12_20_22_30;MX_4_5_13_21_23;MY_10;DT(0,2,0)rec[-17]_rec[-6];DT(6,2,0)rec[-12]_rec[-7];DT(2,0,0)rec[-18]_rec[-11];DT(0,4,0)rec[-19]_rec[-5];DT(4,1,0)rec[-15]_rec[-9]_rec[-3];DT(4,4,0)rec[-14]_rec[-8];DT(4,6,0)rec[-13]_rec[-2];DT(2,3,0)rec[-16]_rec[-10]_rec[-4];OI(0)rec[-9]_rec[-7]_rec[-5]_rec[-4]_rec[-1];SHIFT_COORDS(0,0,1);TICK;R_12_20_22_30;RX_4_13_21_23;TICK;CX_8_12_13_9_17_22_21_16_23_18_25_30;TICK;CX_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;CX_16_12_21_17_26_22;TICK;CX_4_9_13_18_17_12_21_26_25_20_27_22;TICK;M_12_20_22_30;MX_4_13_21_23;DT(4,2,0)rec[-18]_rec[-17]_rec[-11]_rec[-2];DT(6,2,0)rec[-15]_rec[-5];DT(2,2,0)rec[-18]_rec[-8];DT(0,2,0)rec[-14]_rec[-4];DT(4,0,0)rec[-19]_rec[-17]_rec[-7];DT(4,4,0)rec[-16]_rec[-6];DT(4,6,0)rec[-10]_rec[-1];DT(2,4,0)rec[-18]_rec[-13]_rec[-12]_rec[-9]_rec[-3];SHIFT_COORDS(0,0,1);TICK;R_12_20_22_30;RX_4_13_21_23;TICK;CX_8_12_13_9_17_22_21_16_23_18_25_30;TICK;CX_4_8_9_12_13_17_16_20_18_22_21_25_23_27_26_30;TICK;CX_16_12_21_17_26_22;TICK;CX_4_9_13_18_17_12_21_26_25_20_27_22;TICK;M_12_16_20_22_25_26_30;MX_4_8_9_13_17_18_21_23_27;DT(4,6,0)rec[-4]_rec[-2]_rec[-1];DT(2,2,0)rec[-24]_rec[-16];DT(0,2,0)rec[-20]_rec[-9];DT(4,0,0)rec[-23]_rec[-14];DT(4,2,0)rec[-18]_rec[-3];DT(6,2,0)rec[-21]_rec[-10];DT(2,4,0)rec[-19]_rec[-6];DT(4,4,0)rec[-22]_rec[-13];DT(4,6,0)rec[-17]_rec[-2];DT(0,2,0)rec[-9]_rec[-8]_rec[-7];DT(2,4,0)rec[-7]_rec[-6]_rec[-5]_rec[-4];DT(4,0,0)rec[-15]_rec[-14]_rec[-12];DT(6,2,0)rec[-12]_rec[-11]_rec[-10];SHIFT_COORDS(0,0,1)_
.. _zna: https://algassert.com/crumble#circuit=Q(-1,1)0;Q(-1,3)1;Q(-1,5)2;Q(0,0)3;Q(0,2)4;Q(0,4)5;Q(0,6)6;Q(1,-1)7;Q(1,1)8;Q(1,3)9;Q(1,5)10;Q(1,7)11;Q(2,0)12;Q(2,2)13;Q(2,4)14;Q(2,6)15;Q(3,-1)16;Q(3,1)17;Q(3,3)18;Q(3,5)19;Q(3,7)20;Q(4,0)21;Q(4,2)22;Q(4,4)23;Q(4,6)24;Q(5,-1)25;Q(5,1)26;Q(5,3)27;Q(5,5)28;Q(6,0)29;Q(6,2)30;Q(6,4)31;Q(6,6)32;Q(7,3)33;Q(7,5)34;RX_8_12_14_17_18_22_27_28_31;R_5_9_10_13_15_19_23;TICK;CX_10_5_12_17_14_19_18_13_22_27_28_23;TICK;CX_9_13_14_18_19_23;TICK;CX_9_5_12_8_14_10_17_13_19_15_22_18_27_23_31_28;TICK;CX_8_13_10_15_14_9_18_23_22_17_31_27;TICK;MX_12_14_22_31;M_5_13_15_23;DT(6,4,0)rec[-5];DT(2,6,0)rec[-2];DT(0,4,0)rec[-4];DT(4,2,0)rec[-6];DT(2,0,0)rec[-8];SHIFT_COORDS(0,0,1);TICK;RX_12_14_22_31;R_5_13_15_23;TICK;CX_10_5_12_17_14_19_18_13_22_27_28_23;TICK;CX_9_13_14_18_19_23;TICK;CX_9_5_12_8_14_10_17_13_19_15_22_18_27_23_31_28;TICK;CX_8_13_10_15_14_9_18_23_22_17_31_27;TICK;MX_12_14_22_31;M_5_13_15_23;DT(4,2,0)rec[-14]_rec[-6];DT(0,4,0)rec[-12]_rec[-4];DT(2,2,0)rec[-11]_rec[-3];DT(2,0,0)rec[-16]_rec[-8];DT(2,4,0)rec[-15]_rec[-7];DT(4,4,0)rec[-9]_rec[-1];DT(6,4,0)rec[-13]_rec[-5];DT(2,6,0)rec[-10]_rec[-2];SHIFT_COORDS(0,0,1);TICK;RX_12_14_21_22_31;RY_26;R_4_5_13_15_23;TICK;H_4_5_8_9_12_13_17_21;S_DAG_14_22;TICK;CY_10_5_18_13;TICK;CX_9_4_10_15_17_12_18_23_31_27;TICK;CX_5_9_8_12_13_17_19_15_27_23_31_28;CY_14_10_22_18;TICK;CX_4_8_9_13_14_18_17_21_19_23_22_26;TICK;CX_4_9_14_19_18_13_22_27_26_21_28_23;TICK;M_12_13_15_21_23;MX_4_5_14_22_31;DT(0,2,0)rec[-13]_rec[-5];DT(0,4,0)rec[-14]_rec[-4];DT(2,0,0)rec[-18]_rec[-10];DT(4,4,0)rec[-11]_rec[-6];DT(4,1,0)rec[-16]_rec[-7]_rec[-2];DT(6,4,0)rec[-15]_rec[-1];DT(2,6,0)rec[-12]_rec[-8];DT(2,3,0)rec[-17]_rec[-9]_rec[-3];SHIFT_COORDS(0,0,1);TICK;RX_4_13_14_15_21_22_23_31;TICK;CZ_13_8_15_10_23_18;CX_14_9_22_17_31_27;TICK;CX_4_8;CZ_13_17_15_19_23_27;TICK;CZ_13_9_21_17_23_19;CX_14_10_22_18_31_28;TICK;CX_14_18_22_26;TICK;CZ_13_18_21_26_23_28;CX_4_9_14_19_22_27;TICK;MX_4_13_14_15_21_22_23_31;DT(4,2,0)rec[-10]_rec[-3];DT(0,2,0)rec[-13]_rec[-8];DT(4,0,0)rec[-15]_rec[-4];DT(2,2,0)rec[-18]_rec[-17]_rec[-7];DT(4,4,0)rec[-14]_rec[-2];DT(6,4,0)rec[-9]_rec[-1];DT(2,4,0)rec[-12]_rec[-11]_rec[-6];DT(2,6,0)rec[-16]_rec[-5];SHIFT_COORDS(0,0,1);TICK;RX_4_13_14_15_21_22_23_31;TICK;CZ_13_8_15_10_23_18;CX_14_9_22_17_31_27;TICK;CX_4_8;CZ_13_17_15_19_23_27;TICK;CZ_13_9_21_17_23_19;CX_14_10_22_18_31_28;TICK;CX_14_18_22_26;TICK;CZ_13_18_21_26_23_28;CX_4_9_14_19_22_27;TICK;MX_4_13_14_15_21_22_23_31;DT(2,2,0)rec[-15]_rec[-7];DT(4,2,0)rec[-11]_rec[-3];DT(0,2,0)rec[-16]_rec[-8];DT(4,0,0)rec[-12]_rec[-4];DT(2,4,0)rec[-14]_rec[-6];DT(4,4,0)rec[-10]_rec[-2];DT(6,4,0)rec[-9]_rec[-1];DT(2,6,0)rec[-13]_rec[-5];SHIFT_COORDS(0,0,1);TICK;RX_4_13_14_15_21_22_23_31;TICK;CZ_13_8_15_10_23_18;CX_14_9_22_17_31_27;TICK;CX_4_8;CZ_13_17_15_19_23_27;TICK;CZ_13_9_21_17_23_19;CX_14_10_22_18_31_28;TICK;CX_14_18_22_26;TICK;CZ_13_18_21_26_23_28;CX_4_9_14_19_22_27;TICK;MX_4_13_14_15_21_22_23_31;DT(2,2,0)rec[-15]_rec[-7];DT(4,2,0)rec[-11]_rec[-3];DT(0,2,0)rec[-16]_rec[-8];DT(4,0,0)rec[-12]_rec[-4];DT(2,4,0)rec[-14]_rec[-6];DT(4,4,0)rec[-10]_rec[-2];DT(6,4,0)rec[-9]_rec[-1];DT(2,6,0)rec[-13]_rec[-5];SHIFT_COORDS(0,0,1);TICK;R_12_13_15_21_23;RX_4_5_14_22_31;TICK;CX_4_9_14_19_18_13_22_27_26_21_28_23;TICK;CX_4_8_9_13_14_18_17_21_19_23_22_26;TICK;CX_5_9_8_12_13_17_19_15_27_23_31_28;CY_14_10_22_18;TICK;CX_9_4_10_15_17_12_18_23_31_27;TICK;CY_10_5_18_13;TICK;H_4_5_8_9_12_13_17_21;S_14_22;TICK;MX_12_14_21_22_31;MY_26;M_4_5_13_15_23;DT(0,2,0)rec[-19]_rec[-5];DT(4,0,0)rec[-15]_rec[-9];DT(4,4,0)rec[-13]_rec[-1];DT(6,4,0)rec[-12]_rec[-7];DT(2,6,0)rec[-16]_rec[-2];DT(1,4,0)rec[-17]_rec[-10]_rec[-4];DT(2,0,0)rec[-18]_rec[-11];DT(3,2,0)rec[-14]_rec[-8]_rec[-3];OI(0)rec[-9]_rec[-8]_rec[-6]_rec[-4]_rec[-2];SHIFT_COORDS(0,0,1);TICK;RX_12_14_22_31;R_5_13_15_23;TICK;CX_8_13_10_15_14_9_18_23_22_17_31_27;TICK;CX_9_5_12_8_14_10_17_13_19_15_22_18_27_23_31_28;TICK;CX_9_13_14_18_19_23;TICK;CX_10_5_12_17_14_19_18_13_22_27_28_23;TICK;MX_12_14_22_31;M_5_13_15_23;DT(2,2,0)rec[-11]_rec[-3];DT(2,0,0)rec[-19]_rec[-8];DT(2,4,0)rec[-18]_rec[-12]_rec[-11]_rec[-7];DT(4,4,0)rec[-9]_rec[-1];DT(6,4,0)rec[-15]_rec[-5];DT(0,4,0)rec[-13]_rec[-12]_rec[-4];DT(2,6,0)rec[-10]_rec[-2];DT(4,2,0)rec[-17]_rec[-16]_rec[-14]_rec[-11]_rec[-6];SHIFT_COORDS(0,0,1);TICK;RX_12_14_22_31;R_5_13_15_23;TICK;CX_8_13_10_15_14_9_18_23_22_17_31_27;TICK;CX_9_5_12_8_14_10_17_13_19_15_22_18_27_23_31_28;TICK;CX_9_13_14_18_19_23;TICK;CX_10_5_12_17_14_19_18_13_22_27_28_23;TICK;MX_8_12_14_17_18_22_27_28_31;M_5_9_10_13_15_19_23;DT(2,6,0)rec[-5]_rec[-3]_rec[-2];DT(6,4,0)rec[-10]_rec[-9]_rec[-8];DT(4,2,0)rec[-22]_rec[-11];DT(2,2,0)rec[-19]_rec[-4];DT(2,0,0)rec[-24]_rec[-15];DT(0,4,0)rec[-20]_rec[-7];DT(2,4,0)rec[-23]_rec[-14];DT(2,0,0)rec[-16]_rec[-15]_rec[-13];DT(4,4,0)rec[-17]_rec[-1];DT(6,4,0)rec[-21]_rec[-8];DT(2,6,0)rec[-18]_rec[-3];DT(0,4,0)rec[-7]_rec[-6]_rec[-5];DT(4,2,0)rec[-13]_rec[-12]_rec[-11]_rec[-10];SHIFT_COORDS(0,0,1)_

References
----------

.. footbibliography::
