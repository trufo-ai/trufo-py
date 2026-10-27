# Copyright 2025-2026 Trufo, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Start of the trufo-local container: check the settings and folders, install the engine,
then run the service.

Imports nothing from the engine (tfprov), so the checks can run before it is installed.
"""

import base64
import importlib.metadata
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit

from trufo.api.endpoints import TRUFO_API_URL

_DOCS_URL = "https://github.com/trufo-ai/trufo-py/blob/main/docs/trufo_local.md"
_REQUIREMENTS_FILE = Path(__file__).with_name("requirements.txt")


def parse_folder_list(name: str, access: str) -> list[Path]:
    """Return the folders listed in environment variable ``name``, resolved.

    The list is absolute folder paths separated by ":". ``access`` says what the service may do
    in them ("read" or "write to"), for the message when the list is unset.

    Raises:
        ValueError: If the list is unset or empty, or an entry is not an absolute path to an
            existing folder.
    """
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(
            f'{name} is not set. List the folders the service may {access}, separated by ":".'
        )
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


def parse_mount_points(mountinfo: str) -> set[Path]:
    """Return the mount points in ``mountinfo``, the text of ``/proc/<pid>/mountinfo``."""
    # field 5 is the mount point; the kernel writes space, tab, newline and backslash as \ooo
    return {
        Path(re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), line.split()[4]))
        for line in mountinfo.splitlines()
    }


def is_mounted(folder: Path, mount_points: set[Path]) -> bool:
    """Return whether ``folder`` or a folder above it is one of ``mount_points``, other than ``/``."""
    # / is the container's own filesystem, not shared with the host
    return any(path in mount_points for path in (folder, *folder.parents) if path != Path("/"))


def is_trufo_api_url(url: str) -> bool:
    """Return whether ``url`` is an https:// address on trufo.ai or one of its subdomains."""
    try:
        parts = urlsplit(url)
    except ValueError:
        # e.g. an unclosed "[" in the host
        return False
    hostname = parts.hostname or ""
    return parts.scheme == "https" and (hostname == "trufo.ai" or hostname.endswith(".trufo.ai"))


def read_pinned_version() -> str:
    """Return the engine version that requirements.txt pins."""
    return re.match(r"trufo-provenance\[c2pa\]==(\S+) ", _REQUIREMENTS_FILE.read_text())[1]


def _check_index_access(api_key: str) -> None:
    """Exit with a start line if the package index refuses the key or cannot be reached.

    pip reports both, and a missing version, the same way: no matching distribution.
    """
    request = urllib.request.Request("https://packages.trufo.ai/simple/trufo-provenance/")
    credential = base64.b64encode(f"__token__:{api_key}".encode()).decode()
    # unredirected, so a redirect cannot carry the key to another host
    request.add_unredirected_header("Authorization", f"Basic {credential}")
    try:
        # pip's default timeout
        urllib.request.urlopen(request, timeout=15).close()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            sys.exit(
                f"packages.trufo.ai refused TRUFO_SDK_DOWNLOAD_API_KEY (HTTP {exc.code}). "
                "Check that it is an active sdk-download key."
            )
        sys.exit(f"Could not reach packages.trufo.ai: HTTP {exc.code}.")
    except OSError as exc:
        # URLError holds the cause in reason; a timeout while reading the answer is not wrapped
        sys.exit(f"Could not reach packages.trufo.ai: {getattr(exc, 'reason', exc)}.")


def _install_engine(api_key: str) -> None:
    """Install the pinned engine from Trufo's package index, unless this container has it."""
    version = read_pinned_version()
    try:
        installed_version = importlib.metadata.version("trufo-provenance")
    except importlib.metadata.PackageNotFoundError:
        installed_version = None
    if installed_version == version:
        print(f"trufo-provenance {version} is already installed.", file=sys.stderr)
        return
    # the engine's native bridge library cannot load from a noexec mount; tfprov loads without it
    if os.statvfs("/tmp").f_flag & os.ST_NOEXEC:
        sys.exit(f"trufo-provenance {version} cannot run from /tmp. Mount /tmp without noexec.")
    print(f"Installing trufo-provenance {version} from packages.trufo.ai.", file=sys.stderr)
    _check_index_access(api_key)
    # the key reaches pip through its environment only, never its arguments; --quiet keeps
    # pip's index line, which names the index URL, out of the log
    index_url = f"https://__token__:{quote(api_key, safe='')}@packages.trufo.ai/simple/"
    pip = [
        sys.executable,
        "-m",
        "pip",
        "install",
        # into HOME (/tmp), so a read-only root filesystem needs only /tmp mounted
        "--user",
        "--quiet",
        "--no-deps",
        "--require-hashes",
        "--no-cache-dir",
        "--disable-pip-version-check",
        "-r",
        str(_REQUIREMENTS_FILE),
    ]
    if subprocess.run(pip, env={**os.environ, "PIP_INDEX_URL": index_url}).returncode:
        sys.exit(1)


def main() -> None:
    """Check the settings and folders, install the engine, then become the service."""
    trufo_api_url = os.environ.get("TRUFO_API_URL", TRUFO_API_URL)
    if not is_trufo_api_url(trufo_api_url):
        sys.exit(f'TRUFO_API_URL must be an https:// address on trufo.ai, not "{trufo_api_url}".')
    try:
        input_dirs = parse_folder_list("TRUFO_LOCAL_INPUT_DIRS", "read")
        output_dirs = parse_folder_list("TRUFO_LOCAL_OUTPUT_DIRS", "write to")
    except ValueError as exc:
        sys.exit(str(exc))
    mount_points = parse_mount_points(Path("/proc/self/mountinfo").read_text())
    for name, folders in (
        ("TRUFO_LOCAL_INPUT_DIRS", input_dirs),
        ("TRUFO_LOCAL_OUTPUT_DIRS", output_dirs),
    ):
        for folder in folders:
            if not is_mounted(folder, mount_points):
                sys.exit(
                    f"{name}: {folder} is not mounted. "
                    "Mount it at the same path inside the container."
                )
    user = f"{os.getuid()}:{os.getgid()}"
    for folder in input_dirs:
        if not os.access(folder, os.R_OK | os.X_OK):
            sys.exit(
                f"Cannot read input folder {folder} as user {user}. "
                f"See {_DOCS_URL}#folder-permissions"
            )
    for folder in output_dirs:
        if not os.access(folder, os.W_OK | os.X_OK):
            sys.exit(
                f"Cannot write to output folder {folder} as user {user}. "
                f"See {_DOCS_URL}#folder-permissions"
            )
    if not os.access("/tmp", os.W_OK | os.X_OK):
        sys.exit(f"Cannot write to /tmp as user {user}. Mount a writable folder at /tmp.")
    api_key = os.environ.get("TRUFO_SDK_DOWNLOAD_API_KEY", "")
    if not api_key:
        sys.exit("TRUFO_SDK_DOWNLOAD_API_KEY is not set. Set it to your sdk-download key.")
    _install_engine(api_key)
    uvicorn = [sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
    os.execv(sys.executable, uvicorn)


if __name__ == "__main__":
    main()
