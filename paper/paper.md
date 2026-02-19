---
title: 'tqec: A Python package for topological quantum error correction'

authors:
- name: Adrien Suau
  equal_contrib: true
  affiliation: 1
- name: Yiming Zhang
  equal_contrib: true
  affiliation: 2
- name: Purva Thakre
  affiliation: 3
- name: Yilun Zhao
  orcid: 0000-0002-6812-5120
  affiliation: 4
- name: Kabir Dubey
  orcid: 0000-0002-7621-9004
  affiliation: 5
- name: Jose A Bolanos
  affiliation: 6
- name: Arabella Schelpe
  orcid: 0009-0003-9046-3104
  affiliation: 7
- name: Philip Seitz
  orcid: 0000-0003-3856-4090
  affiliation: 8
- name: Gian Giacomo Guerreschi
  affiliation: 9
- name: Ángela Elisa Álvarez Pérez
  affiliation: 10
- name: Reinhard Stahn
  affiliation: 11
- name: Jerome Lensen
  orcid: 0009-0008-7933-6848
  affiliation: 12
- name: Brendan Reid
  affiliation: 13
- name: Austin Fowler
  equal_contrib: true
  affiliation: 14

affiliations:
- name: Qraftware, Toulouse, France
  index: 1
- name: University of Science and Technology of China, China
  index: 2
- name: School of Physics and Applied Physics, Southern Illinois University, Carbondale, USA
  index: 3
- name: Institute of Computing Technology, Chinese Academy of Sciences, China
  index: 4
- name: Department of Computer Science, Northwestern University, United States
  index: 5
- name: Independent Consultant, Finland
  index: 6
- name: Independent Researcher, UK
  index: 7
- name: Technical University of Munich, TUM School of Computation, Information and Technology, Germany
  index: 8
- name: Intel Corporation, Technology Research Group, Santa Clara, USA
  index: 9
- name: Solvy, Spain
  index: 10
- name: Parity Quantum Computing Germany GmbH, Hamburg, Germany
  index: 11
- name: VTT, Finland
  index: 12
- name: PsiQuantum, Palo Alto, California, USA
  index: 13
- name: Stairway Invest, Los Angeles, California, USA
  index: 14

date: 27 August 2025
bibliography: paper.bib

---

# Summary

`tqec` is a Python-based open-source compiler that takes a logical-level quantum
computation model represented as connected 3D primitive blocks and translates it into a detailed,
fault-tolerant, physical-level circuit. The result is a `Stim` circuit with all the detailed
information needed for simulation or to run on real quantum hardware. This enables both quantum algorithm
designers and experimentalists to rapidly iterate and obtain exact low-level circuits, facilitating
efficient performance simulation or experimental demonstration. At present, `tqec` is
primarily centered on the surface code.

# Statement of Need

Simulations of quantum computer operations in the large-scale error correction regime are currently
infeasible. Building the logical `Stim` circuits is a hassle, and Monte Carlo simulations at the scale of,
for example, hierarchical memory systems involving yoked surface codes, are difficult to perform exactly, @gidney:2025.
The full-scale simulations performed by `tqec` provide more accurate fault-tolerant resource estimation
than empirical extrapolations.

`tqec` is designed to be used by students and researchers who seek to understand the theory of quantum
error correction and experiment with scalable quantum computer system and circuit designs. A poster featuring
preliminary research and an educational tutorial enabled by `tqec` have been approved for conference
proceedings: @dubey:2025 and @kan:2025 . A further software package has been recently built to enable better interfacing
between PyZX and `tqec`: @topologiq. The functionality of the `tqec` package is based on several
academic papers (@polian:2015, @fowler:2012, @mcewen:2023, @gidney:2025, @kissinger:2020), and makes
substantial use of Craig Gidney's `Stim` package @gidney:2012.

# State of the Field

The `tqec` library emerged from Austin Fowler's call-to-action presentation at the Munich Quantum Software Forum (@Fowler:2023) which advocated
for an open-source collaborative effort to build software for quantum error correction (QEC). Several software
libraries have been released publicly to attempt to tackle the various challenges related to fault-tolerant compilation. Of the compiler libraries discussed in this section, `tqec` stands out as uniquely positioned to tackle these obstacles. Where many alternatives offer limited functionality or have fallen into disrepair, `tqec` is actively developed and supported by a thriving community.

To our knowledge, the `Lattice Surgery Compiler` by @Watkins:2024 was the first publicly released software to compile
a QASM circuit into lattice surgery operations based on the surface code. While active development on this project has ceased (@LSC), an upgraded version of the compiler was released (@Leblond:2024) to enable hardware aware, resource optimized, DAG-based parallel compilation of lattice surgery instructions for the Clifford + T gate set circuits. @robertsonresourceallocatingcompilerlattice:2025 introduced another surface code lattice surgery compiler that factors in resource estimation to compile quantum computations fault-tolerantly building on the approach presented in @Litinski:2019. This software extends beyond `tqec` by incorporating logical qubit mapping, routing, and allocation; each a critical component of a fully automated compilation pipeline. All three projects employ their own native intermediate representation and gate-level compilation strategies tailored to their research goals, limiting their flexibility. However, unlike `tqec`, these tools do not output `Stim` circuits, which are essential for gauging the performance of Clifford computations before deploying to physical hardware. `tqec` directly represents lattice surgery via its native `BlockGraph` data structure, enabling both manual and automated optimization. Introducing hardware aware compilation capabilities is on the `tqec` roadmap and will be addressed in the future.

`Substrate Scheduler` by @SubstrateS compiles fault tolerant graph states based on the formalism in @Litinski:2019
weighing the tradeoffs between the speed of the computation and qubit overhead in surface code patches. `Substrate Scheduler` was designed
with the goal to minimize the space-time volume of the generated fault-tolerant computation. It is limited to fault-tolerant
compilation of graph states and is no longer under active development.

`Loom Design` by @ELLoom is a software project designed to evaluate the performance of QEC protocols in general. The project contains a built-in library of QEC codes (color codes, surface codes, rotated surface codes, etc.) to implement end-to-end lattice surgery protocols. While `tqec` utilizes multiple spatial junction types and stretched stabilizers for hook error handling in surface codes, `Loom Design` is limited by a generic surface code layout. Compared to the `Loom Design` 3D visualizer, `tqec` also provides support for a comprehensive range of 3D structures enabling automated correlation surface finding.

# Acknowledgements

We thank the Unitary Foundation for a micro-grant in the early stages of the project development.

# References
