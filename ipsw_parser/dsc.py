import logging
import plistlib
from datetime import datetime
from pathlib import Path

from plumbum import local

logger = logging.getLogger(__name__)


def split_dsc(root: Path) -> None:
    """Split dyld shared caches found under ``root`` using ``ipsw dyld split``."""
    ipsw = local["ipsw"]
    dsc_paths = [
        root / "System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64",
        root / "System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64e",
        root / "private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64",
        root / "private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64e",
    ]

    for dsc in dsc_paths:
        if not dsc.exists():
            continue

        logger.info(f"splitting DSC: {dsc}")
        ipsw("dyld", "split", dsc, "-o", root)


def get_device_support_path(product_type: str, product_version: str, product_build_version: str) -> Path:
    """Return the Xcode DeviceSupport path for the given product metadata."""
    device_support_path = Path("~/Library/Developer/Xcode/iOS DeviceSupport").expanduser()
    device_support_path /= f"{product_type} {product_version} ({product_build_version})"
    return device_support_path


def create_device_support_layout(
    product_type: str, product_version: str, product_build_version: str, root_path: Path
) -> Path:
    """Create the Xcode DeviceSupport layout for extracted symbol files."""
    device_support_path = get_device_support_path(product_type, product_version, product_build_version)

    # Split DSC files
    split_dsc(root_path)

    # Clean up the cryptex DSC files after splitting
    cryptex_dsc_dir = root_path / "private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld"
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
