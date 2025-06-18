Running Bluesky on p99
======================

This document outlines three methods for running Bluesky on the p99 beamline: using the `Athena service <#athena>`_, running `Bluesky locally <#local-bluesky>`_, or using a local `blueAPI instance <#local-blueapi>`_.

Athena
------

The Athena service provides a pre-configured Bluesky environment running on a Kubernetes cluster. You can access the blueAPI control interface for Athena `here <https://p99-blueapi.diamond.ac.uk/docs>`__.

For developers who need to access the Kubernetes deployment directly, the landing page is available `here <https://k8s-p99.diamond.ac.uk/>`__. Note that authentication may be required.

Local Bluesky
-------------

For rapid testing and development, running Bluesky locally is often the most convenient approach. A Jupyter Notebook template pre-configured with p99 hardware settings is available at: ``src/p99-bluesky/tests/jupyter_tests/p99_bluesky_template.ipynb``.

To open the template, execute the following command within your activated virtual environment:

.. code::

    jupyter notebook ./tests/jupyter_tests/p99_bluesky_template.ipynb

This notebook provides a starting point for interacting with p99 hardware.

.. warning::

    P99 hardware is only accessible on its dedicated network. The simplest method for testing is to connect to ``p99-ws001`` via SSH:

    .. code::

        ssh -X p99-ws001

.. note::

    Devices are imported from the `dodal <https://github.com/DiamondLightSource/dodal/blob/main/src/dodal/beamlines/p99.py>`__ library. For detailed information on creating new devices, refer to the `ophyd-async <https://blueskyproject.io/ophyd-async/main/tutorials/implementing-devices.html>`__ documentation. 

    The following `flowchart <https://diamondlightsource.github.io/dodal/main/how-to/make-new-ophyd-async-device.html>`__ can assist in determining the appropriate device type.

    Adhering to the `device standards <https://diamondlightsource.github.io/dodal/main/reference/device-standards.html>`__ is crucial when creating new devices.

Local blueAPI
-------------

To run blueAPI locally, you must first start a RabbitMQ instance, you can do this by running the blueAPI script `here <https://github.com/DiamondLightSource/blueapi/blob/main/src/script/start_rabbitmq.sh>`__.


Once RabbitMQ is running, execute the following command from the project root directory:

.. code::

    blueapi --config ./src/yaml_config/blueapi_config.yaml serve

This will start blueAPI with the p99 configuration. To modify the configuration, edit the ``/workspaces/sm-bluesky/src/yaml_config/blueapi_config.yaml`` file.

.. literalinclude:: ../../src/yaml_config/blueapi_config.yaml

.. tip::

    To add custom devices and plans, specify their module paths within the configuration file's ``env.sources`` section:

    For devices (example device path: ``p99_bluesky.devices``):

    .. code::

        env:
            sources:
            - kind: deviceFunctions
                module: p99_bluesky.devices

    For plans (example plans path: ``p99_bluesky.plans``):

    .. code::

        env:
            sources:
            - kind: planFunctions
                module: p99_bluesky.plans

.. note::

    Plans must have a return type of ``MsgGenerator`` from the ``bluesky.protocols`` library and complete type hints for blueAPI to recognize them. For example:

    .. literalinclude:: ../../src/sm_bluesky/common/plans/grid_scan.py
        :start-at: def grid_fast_scan
        :end-at: -> MsgGenerator:
