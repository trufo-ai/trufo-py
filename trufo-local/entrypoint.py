# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Settings checks for the trufo-local container.

Imports nothing from the engine (tfprov), so the checks can run before it is installed.
"""

import os
from pathlib import Path


def parse_folder_list(name: str) -> list[Path]:
    """Return the folders listed in environment variable ``name``, resolved.

    The list is absolute folder paths separated by ":".

    Raises:
        ValueError: If the list is unset or empty, or an entry is not an absolute path to an
            existing folder.
    """
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is not set.")
    folders = []
    for entry in value.split(":"):
        folder = Path(entry)
        if not folder.is_absolute():
            raise ValueError(f'{name}: "{entry}" is not an absolute path.')
        # os.path.isdir answers False where Path.is_dir raises on an unsearchable parent
        if not os.path.isdir(folder):
            raise ValueError(f"{name}: {entry} is not an existing folder.")
        folders.append(folder.resolve())
    return folders
