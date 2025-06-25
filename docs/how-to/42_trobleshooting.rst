Troubleshooting
===============

This section provides solutions to common problems you may encounter.

.. contents::
   :local:
   :depth: 2

Data Writing Issues
~~~~~~~~~~~~~~~~~~~

**Problem:**  
Nexus writer is not writing .nxs file.

**Solution:**  

- Check that the output directory exists and nexus-file-converter services have write permissions.

- Check RabbitMQ configuration to ensure it is correctly set up to handle messages from BlueAPI.

- Add detectors as meta data so that nexus-file-converter pick up the detectors first, rather than let the nexus-file-converter discover them from the data stream.

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
