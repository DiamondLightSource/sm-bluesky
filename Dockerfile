# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
<<<<<<< before updating
FROM ghcr.io/diamondlightsource/ubuntu-devcontainer:noble@sha256:f7fa4c496ab28ebbb919e896fa91a69968831a43270a6d3dd33dec49ad44e9da AS developer
=======
FROM ghcr.io/diamondlightsource/ubuntu-devcontainer:resolute@sha256:94403e378be2ee6d1a351b5753e8bbe887e308a1a3248286febd487a65a41dee AS developer
>>>>>>> after updating

# Add any system dependencies for the developer/build environment here
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    graphviz \
    && apt-get dist-clean
