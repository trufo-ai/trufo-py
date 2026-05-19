# Remote C2PA Signing

Remote signing uses the `trufo` SDK as the public interface and installs the `trufo-provenance` engine as an optional dependency.

Install the provenance extra:

```bash
pip install "trufo[provenance]"
```

Import the remote signing helpers from `trufo` rather than importing `tfprov` directly.

> Full remote signing workflow examples will be added after the phase 5 wrapper API is implemented.
