# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
<<<<<<< before updating
ARG PYTHON_VERSION=3.13@sha256:f489e8b38c2f9fd37a2677244721e04c4afd8bf66cb392b1a3fac9e76f94084f
FROM python:${PYTHON_VERSION} AS developer
=======
FROM ghcr.io/diamondlightsource/ubuntu-devcontainer:noble AS developer
>>>>>>> after updating

# Add any system dependencies for the developer/build environment here
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    graphviz \
    && apt-get dist-clean
