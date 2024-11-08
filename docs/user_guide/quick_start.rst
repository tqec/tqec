Quick start using ``tqec``
==========================

1. Define your computation
--------------------------

The first step should be to define the error-corrected computation you want
to implement. For the sake of simplicity, we will take an error-corrected CNOT
implementation that has been defined using SketchUp and available at
:download:`media/user_guide/logical_cnot.dae <../media/user_guide/logical_cnot.dae>`.

.. only:: builder_html

    You can also interactively visualise the CNOT implementation below.

    .. raw:: html

        <iframe
        src="../_static/media/user_guide/quick_start/logical_cnot.html"
        title="Interactive visualisation of an error-corrected topological CNOT implementation"
        width=100%
        height=500
        ></iframe>

2. Import your computation
--------------------------

In order to use the computation with the ``tqec`` library you need to import it
using ``tqec.BlockGraph``:

.. code-block:: python

    from tqec import BlockGraph

    block_graph = BlockGraph.from_dae_file("logical_cnot.dae")


.. note:: Pre-defined computations

    The ``tqec.gallery`` sub-module contains several pre-defined computation that
    have already been implemented. If you only want to test the library on a simple
    pre-defined computation, you can use to following code:

    .. code-block:: python

        from tqec.gallery.logical_cnot import logical_cnot_block_graph

        block_graph = logical_cnot_block_graph(port_type="Z")


3. Choose the observable(s) of interest
---------------------------------------

The ``tqec`` library can automatically search for valid observables in the
imported computation. To get a list of all the valid observables, you can
use the following code

.. code-block:: python

    observables, correlation_surfaces = block_graph.get_abstract_observables()

Any observable can be plotted using the ``tqec dae2observables`` command line. For our
specific example, the command line

.. code-block:: bash

    tqec dae2observables --out-dir observables/ logical_cnot.dae

should populate the ``observables`` directory with 3 ``.png`` images representing the
3 valid observables found.

4. Compile and export the computation
-------------------------------------

In order to get a ``stim.Circuit`` instance, the computation first need to be compiled.

.. code-block:: python

    from tqec import compile_block_graph

    # You can pick any number of observables from the output of
    # block_graph.get_abstract_observables() and provide them here.
    # In this example, picking only the second observable for demonstration
    # purposes.
    compiled_computation = compile_block_graph(block_graph, observables=[observables[1]])

From this compiled computation, the final ``stim.Circuit`` instance can be generated.

.. code-block:: python

    from tqec.noise_model import NoiseModel

    circuit = compiled_computation.generate_stim_circuit(
        k=2,
        noise_model=NoiseModel.uniform_depolarizing(0.001),
    )

.. note::

    The above call to ``generate_stim_circuit`` also computed automatically
    the detectors and observables that can be added to the computation and added
    them to the generated circuit. If you are using a regular surface code (as we
    are in this quick start guide), the default values for the detectors-related
    parameters should be fine.

And that's all! You now have a quantum circuit representing the topological
error-corrected implementation of a CNOT gate shown at the beginning of this page.

You can download the circuit in a ``stim`` format here:
:download:`media/user_guide/quick_start/logical_cnot.stim <../media/user_guide/quick_start/logical_cnot.stim>`.

6. Simulate multiple experiments
--------------------------------
The circuit can be simulated using the ``stim`` and ``sinter`` libraries.
Usually you want to simulate combinations of error rates and code distances, potentially
for multiple observables.
Multiple runs can be done in parallel using the ``sinter`` library using the
``start_simulation_using_sinter``.
The compilation of the block graph is done automatically based on the inputs.

.. code-block:: python

    from multiprocessing import cpu_count

    import numpy as np

    from tqec.noise_models import NoiseModel
    from tqec.simulation.simulation import start_simulation_using_sinter

    # returns a iterator
    stats = start_simulation_using_sinter(
        block_graph,
        ks=range(1, 4),  # k values for the code distance
        ps=list(np.logspace(-4, -1, 10)),  # error rates
        noise_model_factory=NoiseModel.uniform_depolarizing,  # noise model
        manhattan_radius=2,  # parameter for automatic detector computation
        observables=[observables[1]],  # observable of interest
        decoders=["pymatching"],
        num_workers=cpu_count(),
        max_shots=10_000_000,
        max_errors=5_000,
        print_progress=True,
    )

.. note::
   While ``sinter`` can be supplied with additional simulation parameters, full interoperability with it is not yet implemented.
   See `Sinter API Reference <https://github.com/quantumlib/Stim/blob/main/doc/sinter_api.md>`_ for more information.

.. warning::

    If you happen to copy-paste the above code in an executable Python file, you
    should make sure that you use

    .. code-block:: python

        if __name__ == "__main__":
            ...

    to wrap all the code that might execute the ``sinter`` calls. To know more about
    this issue, have a look at the section "Safe importing of main module" in
    the `multiprocessing module documentation <https://docs.python.org/3/library/multiprocessing.html>`_.

7. Plot the results
-------------------
Simulation results can be plotted with ``matplolib`` using the
``plot_simulation_results``.

.. code-block:: python

    import matplotlib.pyplot as plt
    import sinter

    from tqec.simulation.plotting.inset import plot_observable_as_inset

    zx_graph = block_graph.to_zx_graph()

    fig, ax = plt.subplots()
    # len(stats) = 1 if we have multiple we can iterate over the results
    sinter.plot_error_rate(
        ax=ax,
        stats=next(stats),
        x_func=lambda stat: stat.json_metadata["p"],
        group_func=lambda stat: stat.json_metadata["d"],
    )
    plot_observable_as_inset(ax, zx_graph, correlation_surfaces[1])
    ax.grid(axis="both")
    ax.legend()
    ax.loglog()
    ax.set_title("Logical CNOT Error Rate")
    fig.savefig(f"logical_cnot_result_x_observable_{1}.png")

8. Conclusion
-------------
This quick start guide has shown how to use the ``tqec`` library to define a computation,
import it into the library, compile it to stim circuits.
Simulations are run and visualized for multiple error rates and code distances.
For an extensive example, see also the
`tqec_example <https://github.com/tqec/tqec/blob/main/examples/logical_cnot.py>`_.

The process can be repeated through the cli using

.. code-block:: bash

    tqec run-example --out-dir ./results
