# CLI

The `trufo` CLI provides local credential management and authentication. The tool is meant to help you get started with Trufo API services. The CLI is not meant to be used in production deployments; please use the python

## Setup

The CLI tool is not yet published to PyPI; you can install it with:

```bash
pip install -e /path/to/trufo-py
trufo --help
```

There are a number of environment variables that you may want to set up:
- TPS account API key, for broad account-linked access.
- TSA access key, for making RFC 3161 timestamping requests.
```bash
trufo set-api-key [KEY]
trufo set-tsa-key [KEY]
```

Once the TPS API key is set, you can login:
```bash
trufo login
```
The command prints a verification URL, which you will need to open in a browser. There, you will be instructed to login. Please make sure MFA is set up on your account. For security, when done, you should always logout to clear any refresh tokens:
```bash
trufo logout
```
