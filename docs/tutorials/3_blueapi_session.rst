Interactive BlueAPI Session
===========================

The ``BlueAPISession`` class provides a rich, interactive IPython environment on top of the standard ``BlueapiClient``. It comes pre-configured with automatic data collection callbacks, live plotting, and convenient shortcuts for dispatching plans.

Launching the Session
---------------------

You can launch an interactive session either through the command-line interface or programmatically in Python.

CLI
^^^

Use the ``sm-bluesky client`` command to start a session. You can specify a remote beamline configuration or provide a local YAML config file.

.. code-block:: bash

    # Connect to a remote beamline server (e.g., p99) with a specific session ID
    sm-bluesky client -b p99 -s my_session

    # Connect using a local configuration file
    sm-bluesky client -c ./src/yaml_config/blueapi_config.yaml -s my_session

.. tip::

    If you omit the ``-s`` flag, you will be prompted to provide an instrument session ID, or use ``-d`` for a dummy session.

Programmatically
^^^^^^^^^^^^^^^^

You can also embed the session directly into your own Python scripts or Jupyter Notebooks:

.. code-block:: python

    from sm_bluesky.common.clients import BlueAPISession
    from sm_bluesky.common.cli import load_config

    # Load configuration for a specific beamline
    config = load_config(beamline="p99")
    
    # Initialise the session
    session = BlueAPISession(config=config, instrument_session="my_session")
    
    # Start the interactive IPython shell
    session.start_shell()

The Interactive Shell Environment
---------------------------------

Once the interactive IPython shell is running, you have access to:

* ``bc``: The underlying ``BlueapiClient`` instance.
* ``pl``: A shortcut to access available plans (e.g., ``pl.step_scan(...)``).
* ``dev``: A shortcut to access available devices (e.g., ``dev.dcm``).
* ``show_plan()``: Prints a list of all plans available on the server.
* ``show_devices()``: Prints a list of all devices available on the server.
* ``scan_data``: A dictionary containing all collected event data from your scans.
* ``plot(scan_id=None)``: Opens an interactive visualization window.

Data Collection & Live Plotting
-------------------------------

When you initialise a ``BlueAPISession``, it automatically subscribes to data events from the BlueAPI server. As you run plans, data points are collected and stored in memory.

Accessing Data
^^^^^^^^^^^^^^

Live data is stored in the ``scan_data`` dictionary, which is keyed first by the ``scan_id`` and then by the device name.

.. code-block:: python

    # Run a simple count on the DCM device
    pl.count(dev.dcm)

    # Run a step scan
    # - Detectors: [dev.idd_gap]
    # - Axes & Ranges: [[dev.pgm.energy, [start=200, stop=300, step=1]]]
    pl.step_scan([dev.idd_gap], [[dev.pgm.energy, [200, 300, 1]]])

    # Access the collected data for the last scan
    print(scan_data[<last_scan_num>])
    # You can also get the last scan number by getting the last item in the dictionary
    last_scan_num = next(reversed(scan_data))

Interactive Plotting
^^^^^^^^^^^^^^^^^^^^

You can visualise this data in near real-time using the built-in interactive plot window. By default, the window will attempt to open automatically, but you can also summon it manually:

.. code-block:: python

    # Open the plotting window for the current data
    plot()

.. note::

    The interactive plot window allows you to select which scan to view and choose different axes for your X and Y data directly from the collected device outputs. It polls for new data in the background, keeping your plot updated as the scan progresses.

Session Caching & Variable Persistence
--------------------------------------

The interactive client automatically caches your active session ID and collected scan data so you can seamlessly resume your work after closing the terminal.

Automatic Caching
^^^^^^^^^^^^^^^^^

- **Session ID:** When you launch the client with the ``-s`` flag (e.g., ``sm-bluesky client -b i10 -s my_session``), your session ID is remembered. The next time you launch the client without the ``-s`` flag, it will automatically reconnect to ``my_session``.
- **Scan Data:** Every time a hardware scan completes, the collected data is automatically saved to a local cache (``~/.sm-bluesky/cache/``). When you restart your client and reconnect to the same session, your previous ``scan_data`` is automatically loaded back into memory, allowing you to instantly run ``plot()`` on older scans.

User Variables
^^^^^^^^^^^^^^

There is no easy way to restore the whole namespace as we have active network connections and thread locking is used by the client. Therefore while raw ``scan_data`` is cached automatically, any custom variables or processed data arrays you create must be manually set to be persistent. 

You can save these across sessions using IPython's built-in ``%store`` magic command:

.. tip::

    **Saving a variable:**
    
    .. code-block:: python
    
        # Create a variable
        my_custom_data = scan_data["123"] * 2.5
        
        # Store it to the local IPython cache
        %store my_custom_data

    **Restoring a variable (after restarting the client):**
    
    .. code-block:: python

        # Retrieve the variable from the local IPython cache
        %store -r my_custom_data
        
        print(my_custom_data)

    To view all currently stored variables, simply run ``%store`` without any arguments. You can also restore previously saved variables into your current namespace with ``%store -r``.
