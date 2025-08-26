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
- name: Kabir Dubey
  orcid: 0000-0002-7621-9004
  affiliation: 4
- name: Jose A Bolanos
- name: Arabella Schelpe
- name: Philip Seitz
  orcid: 0000-0003-3856-4090
  affiliation: 5
- name: Gian Giacomo Guerreschi
- name: Ángela Elisa Álvarez Pérez
  affiliation: 6
- name: Reinhard Stahn
  affiliation: 7
- name: Jerome Lensen
  orcid: 0009-0008-7933-6848
  affiliation: 8
- name: Brendan Reid
  affiliation: 9
- name: Austin Fowler
  equal_contrib: true
  affiliation: 10

affiliations:
- name: Qraftware, Toulouse, France
  index: 1
- name: University of Science and Technology of China
  index: 2
- name: School of Physics and Applied Physics, Southern Illinois University, Carbondale, IL, 62901, USA
  index: 3
- name: Department of Computer Science, Northwestern University, United States
  index: 4
- name: Technical University of Munich, TUM School of Computation, Information and Technology
  index: 5
- name: Solvy
  index: 6
- name: Parity Quantum Computing Germany GmbH, 20095 Hamburg, Germany
  index: 7
- name: VTT, Finland
  index: 8
- name: PsiQuantum
  index: 9
- name: Stairway Invest
  index: 10
- name: Institute of Computing Technology, Chinese Academy of Sciences
  index: 11
date: 15 August 2025
bibliography: paper.bib

---

# Summary

`tqec` is a Python-based open-source compiler that takes a logical-level quantum
computation model represented as connected 3D primitive blocks and translates it into a detailed,
fault-tolerant, physical-level circuit. The result is a Stim circuit with all the detailed
information needed for simulation or to run on real quantum hardware. This enables both quantum algorithm
designers and experimentalists to rapidly iterate and obtain exact low-level circuits, facilitating
efficient performance simulation or experimental demonstration. The ‘Topological Quantum Error Correction’
of the package name highlights the project’s focus on topological codes. At present, the project is
primarily centered on the surface code.

# Statement of Need

Simulations of quantum computer operations in the large-scale error correction regime are currently
infeasible. Building the logical Stim circuits is a hassle, and Monte Carlo simulations at the scale of,
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

# Acknowledgements

We thank the Unitary Foundation for a micro-grant in the early stages of the project development.

# References
