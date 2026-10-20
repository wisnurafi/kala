# Docker environment

A reproducible fuzzing environment: the lightweight alternative
to the fuzzing VM, identical everywhere it runs.

```sh
docker build -t kala docker/
docker run --rm -it -v "$PWD":/kala -w /kala kala
```

The image ships clang + libFuzzer, CMake, and the Python runtime
the triage/orchestrate layer needs — the quick start from the root
README works inside the container unchanged.

The VM remains the reference environment for long campaigns (its
setup also builds AFL++ from source). This image intentionally
stays lean: no AFL++, no GUI tooling. Anything a campaign produces
lands in the mounted working tree (`campaigns/`), never inside the
container.
