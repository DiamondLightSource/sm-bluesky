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

.. literalinclude:: ../../src/sm_bluesky/common/plans/fast_scan.py
    :start-at: md["detectors"] = [det.name for det in dets]
    :end-at: def inner_fast_scan_grid


Common Issues
~~~~~~~~~~~~~

.. _installation-issues:

Installation Issues
~~~~~~~~~~~~~~~~~~~

.. _dependency-errors:

Dependency Errors
~~~~~~~~~~~~~~~~~

.. _runtime-errors:
