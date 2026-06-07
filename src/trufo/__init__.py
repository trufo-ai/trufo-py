# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from trufo.api.tps.sign_c2pa import sign_c2pa_remote, sign_c2pa_remote_test

__version__ = "0.3.3"

__all__ = ["__version__", "sign_c2pa_remote", "sign_c2pa_remote_test"]

# register the trufo-py version with tfprov so X-TF-Version is sent on all
# remote calls; no-op if trufo-provenance is not installed
try:
    from tfprov.api.session import set_trufo_version as _set_trufo_version

    _set_trufo_version(__version__)
except ImportError:
    pass
