from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ipsw_parser.ipsw import IPSW

# filename prefix -> component name, as idevicerestore's get_component_name() maps them
_COMPONENT_NAME_PREFIXES = (
    ("LLB", "LLB"),
    ("iBoot", "iBoot"),
    ("DeviceTree", "DeviceTree"),
    ("applelogo", "AppleLogo"),
    ("liquiddetect", "Liquid"),
    ("lowpowermode", "LowPowerWallet0"),
    ("recoverymode", "RecoveryMode"),
    ("batterylow0", "BatteryLow0"),
    ("batterylow1", "BatteryLow1"),
    ("glyphcharging", "BatteryCharging"),
    ("glyphplugin", "BatteryPlugin"),
    ("batterycharging0", "BatteryCharging0"),
    ("batterycharging1", "BatteryCharging1"),
    ("batteryfull", "BatteryFull"),
    ("needservice", "NeedService"),
    ("SCAB", "SCAB"),
    ("sep-firmware", "RestoreSEP"),
)


class Firmware:
    """Helper for firmware manifests and component file mapping."""

    def __init__(self, firmware_path: str, ipsw: "IPSW"):
        """Index firmware manifest entries under a firmware directory."""
        self._ipsw = ipsw
        self._firmware_path = firmware_path
        self._manifest_data = self._ipsw.read(self.get_relative_path("manifest"))
        self._firmware_files: dict[str, str] = {}
        for line in self._manifest_data.decode().splitlines():
            filename = line.strip()
            component_name = self.get_component_name(filename)
            if component_name is None:
                continue
            self._firmware_files[component_name] = f"{firmware_path}/{filename}"

    def get_relative_path(self, path: str) -> str:
        """Return a firmware-relative archive path."""
        return f"{self._firmware_path}/{path}"

    def get_files(self) -> dict[str, str]:
        """Return the indexed firmware component mapping."""
        return self._firmware_files

    @staticmethod
    def get_component_name(filename: str) -> Optional[str]:
        """Map a firmware filename (e.g. ``LLB.n61.RELEASE.img3``) to its component name by its prefix."""
        for prefix, name in _COMPONENT_NAME_PREFIXES:
            if filename.startswith(prefix):
                return name
        return None
