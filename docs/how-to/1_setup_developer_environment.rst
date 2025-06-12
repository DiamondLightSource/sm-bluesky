Setup Developer Environment
===========================

This document outlines the steps to set up a developer environment for the ``sm_bluesky`` project. You can choose to develop within a VSCode devcontainer or using a local virtual environment.

Clone the Repository
--------------------

To clone the repository locally, use `Git <https://git-scm.com/downloads>`__

**SSH (Recommended):**

.. code:: bash

    git clone git@github.com:DiamondLightSource/sm-bluesky.git

**HTTPS:**

.. code:: bash

    git clone https://github.com/DiamondLightSource/sm-bluesky.git

.. tip::

    SSH is the recommended method. To set up SSH keys for Git, follow the instructions : `here. <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account>`__

Install Dependencies
--------------------

You can choose to develop on your host machine using a ``venv`` (Python 3.10 or later required) or within a container using `VSCode <https://code.visualstudio.com/>`__

.. tab-set::

    .. tab-item:: VSCode Devcontainer

        **On a Diamond Light Source terminal:**

        .. code:: bash

            module load vscode
            code ./sm-bluesky

        Once VSCode is running:

        1.  Change the container runtime to Podman (recommended at DLS), press ```Ctrl+Shift+P```type:

            .. code:: bash

                > Dev Containers: Settings

            In the settings, navigate to ``User > Dev > Containers: Docker Path`` and change the value to ``podman``.

        2.  Press ```Ctrl+Shift+P``` (or ``Cmd+Shift+P`` on macOS) or open the command palette and type:

            .. code:: bash

                > Dev Containers: Rebuild Container

            This will build the development container.

        .. tip::

            * For development on Windows, you can use WSL and Docker Desktop. More details are available `here. <https://code.visualstudio.com/docs/devcontainers/containers>`__
            * For setting up VSCode devcontainers outside of Diamond Light Source, refer to this `guide. <https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers>`__

        .. note::

            If you are at DLS and Podman is not set up, follow these `instructions <https://dev-portal.diamond.ac.uk/guide/containers/tutorials/podman/#enable-use-of-vscode-features>`__ to install Podman and configure it for devcontainer features. Then, follow the general devcontainer setup `instructions. <https://dev-portal.diamond.ac.uk/guide/containers/tutorials/devcontainer/>`__.

    .. tab-item:: Local Virtual Environment

        .. code:: bash

            python3.11 -m venv venv_p99
            source venv_p99/bin/activate
            cd sm-bluesky
            pip install -e '.[dev]'
