# Kala fuzzing environment — reproducible alternative to the VM.
# Build:  docker build -t kala docker/
# Run:    docker run --rm -it -v "$PWD":/kala -w /kala kala
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    clang \
    llvm \
    lld \
    cmake \
    ninja-build \
    git \
    python3 \
    python3-pip \
    gdb \
    libssl-dev \
    pkg-config \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# AFL++ is built from source in the VM setup; in Docker it is left as an
# explicit follow-up step so this base image stays small and fast to
# rebuild during Phase 0. libFuzzer ships with clang and works as-is.

WORKDIR /kala
CMD ["bash"]
