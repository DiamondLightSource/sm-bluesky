# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.13@sha256:fb009793d34887badaf75aaf5a37682abebb9fa480ab78134d36b7b19e0812b2
FROM python:${PYTHON_VERSION} AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH
