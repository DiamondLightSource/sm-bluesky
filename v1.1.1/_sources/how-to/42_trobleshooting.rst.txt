Troubleshooting
===============

This section provides solutions to common problems you may encounter.

.. contents::
   :local:
   :depth: 2

Data Writing Issues
~~~~~~~~~~~~~~~~~~~

**Problem:**  
The Nexus writer is not creating a .nxs file.

**Solution:**  

- Ensure that the output directory exists and that the nexus-file-converter service has write permissions.
- Verify that the RabbitMQ configuration is correct and able to handle messages from BlueAPI.
- Add detectors as metadata so that the nexus-file-converter can identify them, rather than relying on discovery from the data stream.

.. code-block:: python

    md["detectors"] = [det.name for det in dets]
    md["motors"] = [scan_motor.name, step_motor.name]
    
Common Issues
~~~~~~~~~~~~~

.. _installation-issues:

Installation Issues
~~~~~~~~~~~~~~~~~~~

.. _dependency-errors:

Dependency Errors
~~~~~~~~~~~~~~~~~

.. _runtime-errors:
