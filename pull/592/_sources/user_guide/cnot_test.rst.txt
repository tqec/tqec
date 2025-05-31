CNOT
=====

This notebook shows the construction and simulation results of the logical CNOT gate between two logical qubits with lattice surgery.


Construction
-------------

A logical CNOT between two logical qubits can be implemented with the help of an ancilla qubit. It can be accomplished by the following steps:

1. $M_{ZZ}$ parity measurement between $Q_{control}$ and $Q_{ancilla}$.
2. $M_{XX}$ parity measurement between $Q_{target}$ and $Q_{ancilla}$.
3. $M_{Z}$ measurement of $Q_{ancilla}$.

``tqec`` provides builtin functions ``tqec.gallery.cnot`` to construct the logical CNOT gate.

.. jupyter-execute::

    from tqec.gallery import cnot

    graph = cnot()
    graph.view_as_html()


The logical CNOT has four independent stabilizer flow generators: :code:`XI -> XX`, :code:`IX -> IX`, :code:`ZI -> ZI`, :code:`IZ -> ZZ`. Here we show the correlation surfaces for the generators.

.. jupyter-execute::

    correlation_surfaces = graph.find_correlation_surfaces()


:code:`XI -> XX`
----------------

.. jupyter-execute::

    graph.view_as_html(
    pop_faces_at_direction="-Y",
    show_correlation_surface=correlation_surfaces[0])


.. jupyter-execute::

    graph.view_as_html(
    pop_faces_at_direction="-Y",
    show_correlation_surface=correlation_surfaces[3])


Example Circuit
----------------
Here we show an example circuit of logical CNOT with $d=3$ surface code that is initialized and measured in X basis

.. jupyter-execute::

    from tqec import compile_block_graph, NoiseModel, Basis

    graph = cnot(Basis.X)
    compiled_graph = compile_block_graph(graph)
    circuit = compiled_graph.generate_stim_circuit(
        k=1, noise_model=NoiseModel.uniform_depolarizing(p=0.001)
    )



.. jupyter-execute::

    import matplotlib.pyplot as plt
    import numpy
    import sinter

    from tqec.gallery.cnot import cnot
    from tqec import NoiseModel
    from tqec.simulation.plotting.inset import plot_observable_as_inset
    from tqec.simulation.simulation import start_simulation_using_sinter
    from tqec.utils.enums import Basis


    def generate_graphs(support_observable_basis: Basis) -> None:
        block_graph = cnot(support_observable_basis)
        zx_graph = block_graph.to_zx_graph()

        correlation_surfaces = block_graph.find_correlation_surfaces()

        stats = start_simulation_using_sinter(
            block_graph,
            range(1, 4),
            list(numpy.logspace(-4, -1, 10)),
            NoiseModel.uniform_depolarizing,
            manhattan_radius=2,
            observables=correlation_surfaces,
            num_workers=20,
            max_shots=10_000_000,
            max_errors=5_000,
            decoders=["pymatching"],
            print_progress=True,
        )

        for i, stat in enumerate(stats):
            fig, ax = plt.subplots()
            sinter.plot_error_rate(
                ax=ax,
                stats=stat,
                x_func=lambda stat: stat.json_metadata["p"],
                group_func=lambda stat: stat.json_metadata["d"],
            )
            plot_observable_as_inset(ax, zx_graph, correlation_surfaces[i])
            ax.grid(axis="both")
            ax.legend()
            ax.loglog()
            ax.set_title("Logical CNOT Error Rate")
            ax.set_xlabel("Physical Error Rate")
            ax.set_ylabel("Logical Error Rate")


.. jupyter-execute::

    generate_graphs(Basis.Z)
