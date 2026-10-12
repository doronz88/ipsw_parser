import logging
import plistlib
from datetime import datetime
from pathlib import Path

from ipsw_parser.process import ProcessExecutionError, run

logger = logging.getLogger(__name__)


DSC_DIRECTORIES = (
    "System/Library/Caches/com.apple.dyld",
    "private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld",
    # Some devices report the cryptex through its /System/Cryptexes/OS symlink instead
    "System/Cryptexes/OS/System/Library/Caches/com.apple.dyld",
)
DSC_NAMES = ("dyld_shared_cache_arm64", "dyld_shared_cache_arm64e")


def split_dsc(root: Path) -> list[Path]:
    """
    Split dyld shared caches found under ``root`` into their images.

    ``ipsw dyld split`` does it using Xcode's own extractor, which refuses a cache whose code
    signature does not match (a patched one, for instance). Such a cache is extracted using
    ``ipsw dyld extract`` instead.

    :returns: The shared caches which were split.
    """
    split: list[Path] = []
    for directory in DSC_DIRECTORIES:
        for name in DSC_NAMES:
            dsc = root / directory / name
            if not dsc.exists():
                continue

            logger.info(f"splitting DSC: {dsc}")
            try:
                run("ipsw", "dyld", "split", dsc, "-o", root)
            except ProcessExecutionError as e:
                logger.warning(f"`ipsw dyld split` failed, extracting the images of {dsc} instead: {e}")
                run("ipsw", "dyld", "extract", dsc, "--all", "--output", root)
            split.append(dsc)
    return split


def get_device_support_path(product_type: str, product_version: str, product_build_version: str) -> Path:
    """Return the Xcode DeviceSupport path for the given product metadata."""
    device_support_path = Path("~/Library/Developer/Xcode/iOS DeviceSupport").expanduser()
    device_support_path /= f"{product_type} {product_version} ({product_build_version})"
    return device_support_path


def create_device_support_layout(
    product_type: str, product_version: str, product_build_version: str, root_path: Path
) -> Path:
    """
    Create the Xcode DeviceSupport layout for extracted symbol files.

    :raises FileNotFoundError: if ``root_path`` holds no dyld shared cache to split.
    """
    device_support_path = get_device_support_path(product_type, product_version, product_build_version)

    # Split DSC files
    if not split_dsc(root_path):
        raise FileNotFoundError(f"no dyld shared cache was found under {root_path}")

    # Clean up the cryptex DSC files after splitting
    for directory in DSC_DIRECTORIES[1:]:
        cryptex_dsc_dir = root_path / directory
        if cryptex_dsc_dir.exists():
            for file in cryptex_dsc_dir.iterdir():
                file.unlink()

    # Create the device support metadata files
    (device_support_path / "Info.plist").write_bytes(
        plistlib.dumps({
            "DSC Extractor Version": "1228.0.0.0.0",
            "DateCollected": datetime.now(),
            "Version": "16.0",
        })
    )
    (device_support_path / ".finalized").write_bytes(plistlib.dumps({}))
    (device_support_path / ".processed_dyld_shared_cache_arm64e").touch()
    (device_support_path / ".processing_lock").touch()

    return device_support_path
