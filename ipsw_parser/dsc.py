import logging
import plistlib
from datetime import datetime
from pathlib import Path

from plumbum import local

logger = logging.getLogger(__name__)


def split_dsc(root: Path) -> None:
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
    """
    Construct the device support directory path.

    Args:
        product_type: Product type (e.g., 'iPhone15,2')
        product_version: Product version (e.g., '16.0')
        product_build_version: Product build version (e.g., '20A362')

    Returns:
        Path to the device support directory
    """
    device_support_path = Path("~/Library/Developer/Xcode/iOS DeviceSupport").expanduser()
    device_support_path /= f"{product_type} {product_version} ({product_build_version})"
    return device_support_path


def create_device_support_layout(
    product_type: str, product_version: str, product_build_version: str, root_path: Path
) -> Path:
    """
    Split DSC and create the "device support" directory layout.

    Args:
        product_type: Product type (e.g., 'iPhone15,2')
        product_version: Product version (e.g., '16.0')
        product_build_version: Product build version (e.g., '20A362')
        root_path: System root path containing the extracted DSC symbols

    Returns:
        Path to the created device support directory
    """
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
