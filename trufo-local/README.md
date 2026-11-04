# trufo-local

The source of the two Docker images at `ghcr.io/trufo-ai/trufo-local`, which run C2PA Signing in Local mode as an HTTP service: the signing-only image (`Dockerfile`) and the full image (`Dockerfile.full`, built on the signing-only image), which adds watermarking. Both start from the `compose.yaml` and `.env.example` here.

To set it up, see [C2PA Signing in Local Mode with the Docker Image](../docs/local/docker.md).
