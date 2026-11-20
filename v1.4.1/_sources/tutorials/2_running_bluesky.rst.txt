Running Bluesky locally
=======================

This document outlines how to run Bluesky locally for rapid testing and development using the provided ``sm-bluesky`` command-line tools. This will run a local instance of BlueAPI alongside a message broker with an ipython interactive environment.

Local BlueAPI with sm-bluesky
-----------------------------

To run blueAPI locally, you must first start a message broker (RabbitMQ/STOMP) to handle live event streaming (This will soon not be necessary). Please follow the instructions at `Start RabbitMQ <https://diamondlightsource.github.io/blueapi/main/tutorials/run-bus.html>`__ to set up your message bus.

.. important::

    Once RabbitMQ is running, you can start the BlueAPI server and connect your client.

Step 1: Start the BlueAPI Server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In a terminal, start the BlueAPI server using your configuration file:

.. code-block:: bash

    sm-bluesky start blueapi --config ./src/yaml_config/blueapi_config.yaml

This will start BlueAPI with your specified configuration. To modify the configuration, edit the ``/workspaces/sm-bluesky/src/yaml_config/blueapi_config.yaml`` file.

.. literalinclude:: ../../src/yaml_config/blueapi_config.yaml

Step 2: Connect to your running server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To connect to a local BlueAPI instance via the interactive client, you can pass your configuration file:

.. code-block:: bash

    sm-bluesky client --config ./src/yaml_config/blueapi_config.yaml -s my_session

.. tip::

    **Remote Option:** If you are connecting to a remote beamline server, you can use the ``-b`` / ``--beamline`` flag instead to connect automatically without a local config file:

    .. code-block:: bash

        sm-bluesky client -b p99 -s cm44186-1

Step 3: Run a Plan
^^^^^^^^^^^^^^^^^^

Once the interactive IPython shell opens, your active session is bound to the ``session`` variable. You can trigger hardware plans directly using the python client:

.. code-block:: python

    # Run a simple count plan on the DCM device
     pl.count(dev.dcm)

Advanced Configurations
-----------------------

.. admonition:: Customizing Devices & Plans

    To add custom devices and plans, specify their module paths within the configuration file's ``env.sources`` section:

    For devices (example device path: ``sm_bluesky.beamlines.p99``):

    .. code-block:: yaml

        env:
            sources:
            - kind: deviceManager
              module: sm_bluesky.beamlines.p99

    For plans (example plans path: ``sm_bluesky.beamlines.p99.plans``):

    .. code-block:: yaml

        env:
            sources:
            - kind: planFunctions
              module: sm_bluesky.beamlines.p99.plans

.. note::

    Plans must have a return type of ``MsgGenerator`` from the ``bluesky.protocols`` library and complete type hints for blueAPI to recognize them. For example:

    .. literalinclude:: ../../src/sm_bluesky/common/plans/grid_scan.py
        :start-at: def grid_fast_scan
        :end-at: -> MsgGenerator:

For a full list of available commands and flags, check out the :doc:`CLI Reference <../how-to/5_cli_documentation>`.
