Running Bluesky locally
=======================

This document outlines how to run Bluesky locally for rapid testing and development using the provided `sm-bluesky` command-line tools. Running a local instance of BlueAPI alongside a message broker gives you full control of an interactive environment.

Local Jupyter Notebooks
-----------------------

For rapid testing and development, running Bluesky locally is often the most convenient approach. A Jupyter Notebook template pre-configured with hardware settings is available at: ``demo/p99/p99_bluesky_template.ipynb``.

To open the template, execute the following command within your activated virtual environment:

.. code::

    jupyter notebook demo/p99/p99_bluesky_template.ipynb

This notebook provides a starting point for interacting with hardware via BlueAPI.

.. note::

    Devices are typically imported from the `dodal <https://github.com/DiamondLightSource/dodal>`__ library. For detailed information on creating new devices, refer to the `ophyd-async <https://blueskyproject.io/ophyd-async/main/tutorials/implementing-devices.html>`__ documentation. 

    Adhering to the `device standards <https://diamondlightsource.github.io/dodal/main/reference/device-standards.html>`__ is crucial when creating new devices.

Local BlueAPI with sm-bluesky
-----------------------------

To run blueAPI locally, you must first start a message broker (RabbitMQ/STOMP) to handle live event streaming. Please follow the instructions at `Start RabbitMQ <https://diamondlightsource.github.io/blueapi/main/tutorials/run-bus.html>`__ to set up your message bus.

Once RabbitMQ is running, you can start the BlueAPI server and connect your client.

1. In a terminal, start the BlueAPI server using your configuration file:

.. code::

    sm-bluesky start blueapi --config ./src/yaml_config/blueapi_config.yaml

This will start BlueAPI with your specified configuration. To modify the configuration, edit the ``/workspaces/sm-bluesky/src/yaml_config/blueapi_config.yaml`` file.

.. literalinclude:: ../../src/yaml_config/blueapi_config.yaml

2. Connect to your running server via the interactive client:

To connect to a local BlueAPI instance, you can pass your configuration file:

.. code::

    sm-bluesky client --config ./src/yaml_config/blueapi_config.yaml -s my_session

**Remote Option:** If you are connecting to a remote beamline server, you can use the ``-b`` / ``--beamline`` flag instead to connect automatically without a local config file:

.. code::

    sm-bluesky client -b p99 -s cm44186-1

.. tip::

    To add custom devices and plans, specify their module paths within the configuration file's ``env.sources`` section:

    For devices (example device path: ``sm_bluesky.beamlines.p99``):

    .. code::

        env:
            sources:
            - kind: deviceManager
              module: sm_bluesky.beamlines.p99

    For plans (example plans path: ``sm_bluesky.beamlines.p99.plans``):

    .. code::

        env:
            sources:
            - kind: planFunctions
              module: sm_bluesky.beamlines.p99.plans

.. note::

    Plans must have a return type of ``MsgGenerator`` from the ``bluesky.protocols`` library and complete type hints for blueAPI to recognize them. For example:

    .. literalinclude:: ../../src/sm_bluesky/common/plans/grid_scan.py
        :start-at: def grid_fast_scan
        :end-at: -> MsgGenerator:
