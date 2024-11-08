# TQEC

TQEC(Topological Quantum Error Correction) is a design automation software for representing,
constructing and compiling large-scale fault-tolerant quantum computations based on surface code and lattice surgery.

In the past decade, there have been significant advancements in surface code quantum computation based on lattice surgery.
However, the circuits required to implement these protocols are highly complex. To combine these protocols for constructing larger-scale computation,
a substantial amount of effort is needed to manually encode the circuits, and it is extremely challenging to ensure their correctness.
As a result, many complex logical computations have not been practically simulated.

`tqec` provides numerous building blocks based on state-of-the-art protocols, with verified correct circuits implementation for each block.
These blocks can then be combined to construct large-scale logical computations, enabling the automatic compilation of large-scale computational circuits.

**Note:** This project is under active development and provide no backwards compatibility at current stage.

## Documentation

Documentation is available at <https://qchackers.github.io/tqec/>

## Installation

Currently, you need to install `tqec` from source:

```sh
python -m pip install git+https://github.com/tqec/tqec.git
```

For a more detailed installation guide and common troubleshooting tips, see the [installation page](https://tqec.github.io/tqec/user_guide/installation.html) in the documentation.

## Basic Usage

Here we generate the circuits for a logical CNOT between two logical qubits to demonstrate how to use the tool.
Refer to [quick start](https://tqec.github.io/tqec/user_guide/quick_start.html) in the documentation for more detailed explanation.

```py
from tqec import BlockGraph, compile_block_graph
from tqec.noise_model import NoiseModel

# 1. Construct the logical computation
block_graph = BlockGraph.from_dae_file("assets/logical_cnot.dae")

# 2. Get the logical observables of interests and compile the computation
observables, _ = block_graph.get_abstract_observables()
compiled_computation = compile_block_graph(block_graph, observables=[observables[1]])

# 3. Generate the `stim.Circuit` of target code distance
circuit = compiled_computation.generate_stim_circuit(
    # k = (d-1)/2 is the scale factor
    # Large values will take a lot of time.
    k=2,
    # The noise applied and noise levels can be changed.
    noise_model=NoiseModel.uniform_depolarizing(0.001),
)
```

See the [quick start tutorial](https://tqec.github.io/tqec/quick_start.html) for a
more in-depth explanation.

## Contributing

Pull requests and issues are more than welcomed!

See the [contributing page](https://tqec.github.io/tqec/contributor_guide.html) for for specific instructions to start contributing.

## Community

Every Wednesday, we hold [meetings](https://calendar.google.com/calendar/event?action=TEMPLATE&tmeid=Mmw3NHVqZjRvaWo0bzl2bWtpamE0cmV0NzJfMjAyNDEwMzBUMTUzMDAwWiBhdXN0aW5nZm93bGVyQG0&tmsrc=austingfowler%40gmail.com&scp=ALL) to discuss project progress and conduct educational talks related to TQEC.

Here are some helpful links to learn more about the community:

- Overview of state of the art 2D QEC: [Slides](https://docs.google.com/presentation/d/1xYBfkVMpA1YEVhpgTZpKvY8zeOO1VyHmRWvx_kDJEU8/edit?usp=sharing)/[Video](https://www.youtube.com/watch?v=aUtH7wdwBAM&t=2s)
- Community questions and answers: [Docs](https://docs.google.com/document/d/1VRBPU5eMGVEcxzgHccd98Ooa7geHGRWJoN_fdB1VClM/edit?usp=sharing)
- Introduction to surface code quantum computation: [Slides](https://docs.google.com/presentation/d/1GxGD9kzDYJA6X47BXGII2qjDVVoub5BsSVrGHRZINO4/edit?usp=sharing)
- Programming a quantum computer using SketchUp: [Slides](https://docs.google.com/presentation/d/1MjFuODipnmF-jDstEnQrqbsOtbSKZyPsuTOMo8wpSJc/edit#slide=id.p)/[Video](https://drive.google.com/file/d/1o1LMiidtYDcVoEFZXsJPb7XdTkZ83VFX/view?usp=drive_link)

Please join the [Google group](https://groups.google.com/g/tqec-design-automation) to receive more updates and information!
