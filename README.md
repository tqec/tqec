*This is a rapidly evolving project - documentation and materials from previous recordings may become outdated quickly. If you encounter any inconsistencies or have questions, please [open an issue](https://github.com/tqec/tqec/issues/new/choose).*

---

# TQEC

![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
[![build](https://github.com/tqec/tqec/actions/workflows/ci.yml/badge.svg)](https://github.com/tqec/tqec/actions/workflows/ci.yml)
[![docs](https://github.com/tqec/tqec/actions/workflows/gh-pages.yml/badge.svg)](https://github.com/tqec/tqec/actions/workflows/gh-pages.yml)
[![Stars](https://img.shields.io/github/stars/tqec/tqec.svg)](https://github.com/tqec/tqec/stargazers)
[![Star History Chart](https://img.shields.io/badge/📈-Star%20History-blue?style=flat-square)](https://www.star-history.com/#tqec/tqec&Date)
[![Ethical Notice](https://img.shields.io/badge/docs-ethical%20notice-blue)](https://tqec.github.io/tqec/ethical_notice.html)
[![Licensed under the Apache 2.0 open-source license](https://img.shields.io/badge/License-Apache%202.0-blue.svg?logo=opensourceinitiative)](https://github.com/tqec/tqec/blob/main/LICENSE)

TQEC (Topological Quantum Error Correction) is a design automation software for representing,
constructing and compiling large-scale fault-tolerant quantum computations based on surface code and lattice surgery.

In the past decade, there have been significant advancements in surface code quantum computation based on lattice surgery.
However, the circuits required to implement these protocols are highly complex. To combine these protocols for constructing larger-scale computation,
a substantial amount of effort is needed to manually encode the circuits, and it is extremely challenging to ensure their correctness.
As a result, many complex logical computations have not been practically simulated.

`tqec` provides numerous building blocks based on state-of-the-art protocols, with verified correct circuits implementation for each block.
These blocks can then be combined to construct large-scale logical computations, enabling the automatic compilation of large-scale computational circuits.

> **_NOTE:_** This project is under active development and provide no backwards compatibility at current stage.

<p align="center">
  <a href="https://tqec.github.io/tqec/">
  <img width=30% src="https://img.shields.io/badge/documentation-blue?style=for-the-badge&logo=read%20the%20docs" alt="Documentation" />
  </a>
</p>

Documentation is available at <https://tqec.github.io/tqec/index.html>

## Installation

Currently, you need to install `tqec` from source with `pip` or [`uv`](https://docs.astral.sh/uv/):

**With pip:**
```bash
python -m pip install git+https://github.com/tqec/tqec.git
```

**With uv:**
```bash
uv pip install git+https://github.com/tqec/tqec.git
```

For a more detailed installation guide and common troubleshooting tips, see the [installation page](https://tqec.github.io/tqec/user_guide/installation.html) in the documentation.

## Basic Usage

Here we generate the circuits for a logical CNOT between two logical qubits to demonstrate how to use the tool.
Refer to [quick start](https://tqec.github.io/tqec/user_guide/quick_start.html) in the documentation for more detailed explanation.

```py
from pathlib import Path

from tqec import BlockGraph, compile_block_graph, NoiseModel

# 0. Path to the logical_cnot.dae file
cnot_dae_filepath = Path.cwd() / "assets" / "logical_cnot.dae"
if not cnot_dae_filepath.exists():
    print(f"The file '{cnot_dae_filepath}' does not exist.")

# 1. Construct the logical computation
block_graph = BlockGraph.from_dae_file(cnot_dae_filepath)

# 2. Get the correlation surfaces of interest and compile the computation
correlation_surfaces = block_graph.find_correlation_surfaces()
compiled_computation = compile_block_graph(block_graph, observables=[correlation_surfaces[1]])

# 3. Generate the `stim.Circuit` of target code distance
circuit = compiled_computation.generate_stim_circuit(
    # k = (d-1)/2 is the scale factor
    # Large values will take a lot of time.
    k=2,
    # The noise applied and noise levels can be changed.
    noise_model=NoiseModel.uniform_depolarizing(0.001),
)
```

See the [user guide](https://tqec.github.io/tqec/user_guide/index.html) for more tutorials.

## Contributing

Pull requests and issues are more than welcomed!

See the [contributing page](https://tqec.github.io/tqec/contributor_guide.html) for for specific instructions to start contributing.

## Community

Every Wednesday at 8:30am PST, we hold [meetings](https://meet.jit.si/TQEC-design-automation) to discuss project progress and conduct educational talks related to TQEC.

Here are some helpful links to learn more about the community:

- Overview of state of the art 2D QEC: [Slides](https://docs.google.com/presentation/d/1xYBfkVMpA1YEVhpgTZpKvY8zeOO1VyHmRWvx_kDJEU8/edit?usp=sharing)/[Video](https://www.youtube.com/watch?v=aUtH7wdwBAM&t=2s)
- Community questions and answers: [Docs](https://docs.google.com/document/d/1VRBPU5eMGVEcxzgHccd98Ooa7geHGRWJoN_fdB1VClM/edit?usp=sharing)
- Introduction to surface code quantum computation: [Slides](https://docs.google.com/presentation/d/1GxGD9kzDYJA6X47BXGII2qjDVVoub5BsSVrGHRZINO4/edit?usp=sharing)
- Programming a quantum computer using SketchUp: [Slides](https://docs.google.com/presentation/d/1MjFuODipnmF-jDstEnQrqbsOtbSKZyPsuTOMo8wpSJc/edit?usp=sharing)/[Video](https://drive.google.com/file/d/1o1LMiidtYDcVoEFZXsJPb7XdTkZ83VFX/view?usp=drive_link)

All the resources and group meeting recordings are available at [this link](https://docs.google.com/spreadsheets/d/11DSA2wzKLOrfTGNHunFvzsMYeO7jZ8Ny8kpzoC_wKQg/edit?usp=sharing&resourcekey=0-PdGFkp5s-4XWihMSxk0UIg).

Please join the [Google group](https://groups.google.com/g/tqec-design-automation) to receive more updates and information!

---
> ### **Ethical notice**
>
> This library is intended for **academic, educational, and civilian research only**, in the field of **fault-tolerant quantum computing**, particularly in **surface code compilation** and **topological error correction**.
>
> It is made freely and publicly available without access restrictions, in the interest of advancing **open scientific and academic collaboration**.
>
> The maintainers request that users and contributors **refrain from engaging in, supporting, or facilitating military, surveillance, or dual-use applications**.
>
> Please, review the full [`ETHICAL_NOTICE.md`](https://github.com/tqec/tqec/blob/main/ETHICAL_NOTICE.md) for important terms regarding **export control**, **ethical use**, and **contributor responsibilities**.
---
