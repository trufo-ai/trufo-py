# CLI

The `trufo` CLI provides local credential management and authentication. The tool is meant to help you get started with Trufo API services. The CLI is not meant to be used in production deployments; please use the python

## Setup

```bash
pip install trufo
trufo --help
```

There are a number of API keys you will want to set up (see [api/api_auth.md](api/api_auth.md) for more details):

```bash
trufo set-api-key trufo-api      [KEY] # device authorization flow
trufo set-api-key c2pa-sign-prod [KEY] # POST /c2pa/sign
trufo set-api-key c2pa-sign-test [KEY] # POST /test/c2pa/sign
trufo set-api-key tsa            [KEY] # tsa.trufo.ai
```

Once the `trufo-api` key is set, you can login:
```bash
trufo login
```
The command prints a verification URL, which you will need to open in a browser. There, you will be instructed to login. Please make sure MFA is set up on your account. For security, when done, you should always logout to clear any refresh tokens:
```bash
trufo logout
```
