#!/usr/bin/env python3
"""Install a pinned official Stockfish release using only the standard library."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen
import zipfile

VERSION = "sf_19"
ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "engines" / "stockfish"
# SHA-256 digests published by the official GitHub release.
ASSETS = {
    ("Linux", "x86_64"): ("stockfish-linux-x86-64-universal.tar.gz", "9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f"),
    ("Linux", "aarch64"): ("stockfish-linux-arm64-universal.tar.gz", "fe26cfd1d9db4c8af3d21e24d9ff34cacb31c1f940085a7583da11796f2bac01"),
    ("Darwin", "x86_64"): ("stockfish-macos-universal.tar.gz", "a1f0e3bcc5a6927a11fe6fc8e54a779754645f3c2bae2cf13420fd1957adaa77"),
    ("Darwin", "aarch64"): ("stockfish-macos-universal.tar.gz", "a1f0e3bcc5a6927a11fe6fc8e54a779754645f3c2bae2cf13420fd1957adaa77"),
    ("Windows", "x86_64"): ("stockfish-windows-x86-64-universal.zip", "3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7"),
    ("Windows", "aarch64"): ("stockfish-windows-arm64-universal.zip", "8372ad3f0d7276deb2c70f801f541ec7db463219fc6d9c7592864e542aa4f401"),
}


def safe_target(destination, name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError(f"Unsafe archive path: {name}")
    return destination.joinpath(*path.parts)


def unpack(archive, destination):
    # Extract regular files only; no archive-controlled links or special files.
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                target = safe_target(destination, member.filename)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
    else:
        with tarfile.open(archive) as bundle:
            for member in bundle:
                target = safe_target(destination, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                else:
                    raise ValueError(f"Unsupported archive member: {member.name}")


def verify_engine(executable):
    result = subprocess.run(
        [str(executable)], input="uci\nquit\n", text=True,
        capture_output=True, timeout=30, check=True,
    )
    if "uciok" not in result.stdout or "Stockfish 19" not in result.stdout:
        raise RuntimeError("Stockfish did not complete its UCI handshake.")


def install():
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    asset = ASSETS.get((platform.system(), machine))
    if asset is None:
        raise RuntimeError(
            f"Unsupported platform: {platform.system()} {machine}. "
            "Install Stockfish manually and set STOCKFISH_PATH."
        )
    filename, digest = asset
    executable_name = "stockfish.exe" if os.name == "nt" else "stockfish"
    executable = DESTINATION / executable_name
    if DESTINATION.exists():
        marker = DESTINATION / "VERSION"
        if marker.is_file() and marker.read_text().strip() == f"{VERSION} {filename}":
            verify_engine(executable)
            print(f"Already installed: {executable}")
            return
        raise RuntimeError(f"{DESTINATION} already exists with a different/incomplete installation. Rename it before installing.")

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/official-stockfish/Stockfish/releases/download/{VERSION}/{filename}"
    print(f"Downloading {url}", flush=True)
    with tempfile.TemporaryDirectory(prefix="stockfish-", dir=DESTINATION.parent) as temp:
        temporary = Path(temp)
        archive = temporary / filename
        checksum = hashlib.sha256()
        with urlopen(url, timeout=60) as response, archive.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                checksum.update(chunk)
                output.write(chunk)
        if checksum.hexdigest() != digest:
            raise RuntimeError("SHA-256 verification failed; nothing has been installed.")
        unpack(archive, temporary / "unpacked")
        bundle = temporary / "unpacked" / "stockfish"
        binary_name = filename.removesuffix(".tar.gz").removesuffix(".zip")
        if os.name == "nt":
            binary_name += ".exe"
        binary = bundle / binary_name
        binary.rename(bundle / executable_name)
        (bundle / executable_name).chmod(0o755)
        verify_engine(bundle / executable_name)
        (bundle / "VERSION").write_text(f"{VERSION} {filename}\n", encoding="utf-8")
        bundle.rename(DESTINATION)
    print(f"Installed: {executable}")


if __name__ == "__main__":
    try:
        install()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        sys.exit(1)
