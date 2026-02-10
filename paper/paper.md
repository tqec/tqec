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

The `tqec` library emerged from Austin Fowler's call-to-action presentation @Fowler:2023 which advocated
for an open-source collaborative effort to build software for quantum error correction (QEC). Several software
libraries have been released publicly to attempt to tackle the various challenges in lattice surgery compilation. Although,
`tqec` is uniquely positioned to tackle these challenges compared to the limited functionality of the other compiler
libraries.

To our knowledge, the `Lattice Surgery Compiler` @Watkins:2024 was the first publicly released software to compile
a QASM circuit into lattice surgery operations based on the surface code. The accompanying software package @LSC was last
updated three years ago and attempts to use the project (especially their web UI) have not been straightforward
(to do: rephrase this sentence in a positive way). The project's output is in machine readable format rather than a `Stim` circuit
which allows a user to simulate the performance of their Clifford based computation before sending the generated computation to
a physical device. `Substrate Scheduler` @SubstrateS compiles fault tolerant graph states based on Litinski's @Litinski:2019 formalism
weighing the tradeoffs between the speed of the computation and qubit overhead in surface code patches. `Substrate Scheduler` was designed
with the goal to minimize the space-time volume of the generated fault-tolerant computation. However, it is limited by it's ability
to only accept graph states as input. `Loom Design` @ELLoom is another software project designed to evaluate the performance of QEC
protocols. The project contains an in-built library of pre-built QEC codes such that it is easier to compile lattice surgery protocols
beyond the surface code. (Add more here)

# Acknowledgements

We thank the Unitary Foundation for a micro-grant in the early stages of the project development.

# References
