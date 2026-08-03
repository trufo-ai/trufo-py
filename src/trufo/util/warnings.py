# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Warning categories raised by the Trufo SDK."""

import warnings


class TrufoServerWarning(UserWarning):
    """A non-fatal notice returned by a Trufo endpoint.

    Raised when the server completed the request but skipped something the
    caller asked for — e.g. a lenient ``watermark`` effort that could not
    embed, or a deprecated SDK version. Its own category, so callers can act
    on these precisely::

        import warnings
        from trufo import TrufoServerWarning, sign_c2pa

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", TrufoServerWarning)
            signed = sign_c2pa(api_key, media_bytes, actions=actions)
        if caught:
            ...  # e.g. re-queue, alert, or record the unwatermarked output
    """


def emit_server_warnings(payload: dict) -> None:
    """Re-emit an API response's ``warnings`` as :class:`TrufoServerWarning`.

    The distributed flow emits the same server notices through ``warnings``,
    so both signing modes surface them identically.
    """
    for message in payload.get("warnings") or []:
        warnings.warn(str(message), TrufoServerWarning, stacklevel=3)
