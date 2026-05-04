class Firmware:
    """Helper for firmware manifests and component file mapping."""

    def __init__(self, firmware_path: str, ipsw):
        """Index firmware manifest entries under a firmware directory."""
        self._ipsw = ipsw
        self._firmware_path = firmware_path
        self._manifest_data = self._ipsw.read(self.get_relative_path("manifest"))
        self._firmware_files = {}
        for filename in self._manifest_data.splitlines():
            filename = filename.strip()
            component_name = self.get_component_name(filename)
            self._firmware_files[component_name] = f"{firmware_path}/{filename}"

    def get_relative_path(self, path: str):
        """Return a firmware-relative archive path."""
        return f"{self._firmware_path}/{path}"

    def get_files(self):
        """Return the indexed firmware component mapping."""
        return self._firmware_files

    @staticmethod
    def get_component_name(filename):
        """Map a firmware filename to its logical component name."""
        names = {
            "LLB": "LLB",
            "iBoot": "iBoot",
            "DeviceTree": "DeviceTree",
            "applelogo": "AppleLogo",
            "liquiddetect": "Liquid",
            "lowpowermode": "LowPowerWallet0",
            "recoverymode": "RecoveryMode",
            "batterylow0": "BatteryLow0",
            "batterylow1": "BatteryLow1",
            "glyphcharging": "BatteryCharging",
            "glyphplugin": "BatteryPlugin",
            "batterycharging0": "BatteryCharging0",
            "batterycharging1": "BatteryCharging1",
            "batteryfull": "BatteryFull",
            "needservice": "NeedService",
            "SCAB": "SCAB",
            "sep-firmware": "RestoreSEP",
        }
        return names.get(filename)
