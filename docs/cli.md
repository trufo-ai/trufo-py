# CLI

The `trufo` CLI provides local credential management and authentication. The tool is meant to help you get started with Trufo API services. The CLI is not meant to be used in production deployments; please use the Python API directly.

## Setup

```bash
pip install trufo
trufo --help
```

There are a number of API keys you will want to set up (see [api_trufo.md](api/api_trufo.md) for more details):

```bash
trufo set-api-key trufo-api      [KEY] # required for `trufo login`
trufo set-api-key c2pa-sign-prod [KEY] # POST /c2pa/sign
trufo set-api-key c2pa-sign-test [KEY] # POST /c2pa/sign (test host)
trufo set-api-key content-recover-prod [KEY] # POST /content/recover
trufo set-api-key content-recover-test [KEY] # POST /content/recover (test host)
trufo set-api-key tsa            [KEY] # tsa.trufo.ai
```

The `trufo-api` key must be set **before** you log in — `trufo login` authenticates with it, and exits with `No trufo-api key configured` otherwise. Once it is set:
```bash
trufo login
```
This opens a browser on the same machine and signs you in — nothing to type. Please make sure MFA is set up on your account.

If the CLI and your browser are on different machines (over SSH, or in a container), a local browser cannot receive the result. Use the device flow instead, which prints a URL and a code to confirm in any browser:
```bash
trufo login --device
```
The CLI falls back to this automatically when it cannot open a local listener.

For security, when done, you should always logout to clear any refresh tokens:
```bash
trufo logout
```
