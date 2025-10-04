tqec CLI
=========

The following provide example scripts of the tqec CLI.

Check DAE
---------

.. code-block:: bash

    #!/usr/bin/env bash

    PARENT_PATH=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
    EXAMPLE_PATH=$(dirname "$PARENT_PATH")
    TQEC_PATH=$(dirname "$EXAMPLE_PATH")
    ASSETS_PATH=$(dirname "$TQEC_PATH")

    tqec check_dae "${ASSETS_PATH}/logical_cnot.dae"



DAE to circuits
----------------

.. code-block:: bash

    #!/usr/bin/env bash

    PARENT_PATH=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
    EXAMPLE_PATH=$(dirname "$PARENT_PATH")
    TQEC_PATH=$(dirname "$EXAMPLE_PATH")
    ASSETS_PATH=$(dirname "$TQEC_PATH")

    tqec dae2circuits "${ASSETS_PATH}/logical_cnot.dae" \
    --out-dir out \
    -k 1 2 3 \
    --obs-include 0 \
    --add-detectors


DAE to observables
------------------

.. code-block:: bash

    #!/usr/bin/env bash

    PARENT_PATH=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
    EXAMPLE_PATH=$(dirname "$PARENT_PATH")
    TQEC_PATH=$(dirname "$EXAMPLE_PATH")
    ASSETS_PATH=$(dirname "$TQEC_PATH")

    tqec dae2observables "${ASSETS_PATH}/logical_cnot.dae" \
    --out-dir out
