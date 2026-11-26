# CLI Reference

The `trufo` package installs a small credential-management CLI for local development. For servers and CI, prefer environment variables (see [Setup and Credentials](../topics/setup.md)).

## Credential Commands

```bash
# Store a scoped API key in ~/.trufo/credentials/<scope>_api_key (mode 0600 on POSIX)
trufo set-api-key <scope> <api-key>

# Sign in via browser (loopback PKCE) and save tokens to ~/.trufo/session
# Requires a configured trufo-api key
trufo login

# Sign in using the OAuth 2.0 device flow (SSH, containers, headless machines)
trufo login --device

# Clear the local session file
trufo logout
```

Valid `<scope>` values: `trufo-api`, `c2pa-sign-prod`, `c2pa-sign-test`, `watermark-prod`, `watermark-test`, `content-recover-prod`, `content-recover-test`, `tsa`.

Run `trufo --help` for the full list of commands installed with your version of `trufo`.
