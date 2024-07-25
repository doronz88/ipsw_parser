import logging
import shutil
from collections import UserDict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Mapping, Optional

from cached_property import cached_property
from plumbum import local

from ipsw_parser.component import Component

logger = logging.getLogger(__name__)


def _extract_dmg(buf: bytes, output: Path, sub_path: Optional[Path] = None) -> None:
    ipsw = local['ipsw']
    hdiutil = local['hdiutil']
    # darwin system statistically have problems cleaning up after detaching the mountpoint
    with TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        mnt = temp_dir / 'mnt'
        mnt.mkdir()
        dmg = temp_dir / 'image.dmg'

        if buf.startswith(b'AEA1'):
            logger.debug('Found Apple Encrypted Archive. Decrypting...')
            dmg_aea = Path(str(dmg) + '.aea')
            dmg_aea.write_bytes(buf)
            ipsw('fw', 'aea', dmg_aea, '-o', temp_dir)
        else:
            dmg.write_bytes(buf)

        hdiutil('attach', '-mountpoint', mnt, dmg)

        try:
            if sub_path is None:
                src = mnt
            else:
                src = mnt / sub_path
            shutil.copytree(src, output, symlinks=True, dirs_exist_ok=True)
        except shutil.Error:
            # when overwriting the same files, some of them don't contain write permissions
            pass

        hdiutil('detach', '-force', mnt)


def _split_dsc(root: Path) -> None:
    ipsw = local['ipsw']
    dsc_paths = [
        root / 'System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64',
        root / 'System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64e',
        root / 'private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64',
        root / 'private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64e']

    for dsc in dsc_paths:
        if not dsc.exists():
            continue

        logger.info(f'splitting DSC: {dsc}')
        ipsw('dyld', 'split', dsc, '-o', root)


class BuildIdentity(UserDict):
    def __init__(self, build_manifest, data):
        super().__init__(data)
        self.build_manifest = build_manifest

    @cached_property
    def device_class(self) -> str:
        return self['Info']['DeviceClass'].lower()

    @cached_property
    def restore_behavior(self) -> str:
        return self['Info'].get('RestoreBehavior')

    @cached_property
    def variant(self):
        return self['Info'].get('Variant')

    @cached_property
    def macos_variant(self) -> str:
        return self['Info'].get('MacOSVariant')

    @cached_property
    def manifest(self) -> Mapping:
        return self['Manifest']

    @cached_property
    def minimum_system_partition(self):
        return self['Info'].get('MinimumSystemPartition')

    def get_component_path(self, component: str) -> str:
        return self.manifest[component]['Info']['Path']

    def has_component(self, name: str) -> bool:
        return name in self.manifest

    def get_component(self, name: str, **args) -> Component:
        return Component(self, name, **args)

    def populate_tss_request_parameters(self, parameters: Mapping, additional_keys: List[str] = None):
        """ equivalent to idevicerestore:tss_parameters_add_from_manifest """
        key_list = ['ApBoardID', 'ApChipID']
        if additional_keys is None:
            key_list += ['UniqueBuildID', 'Ap,OSLongVersion', 'Ap,OSReleaseType', 'Ap,ProductType', 'Ap,SDKPlatform',
                         'Ap,SikaFuse', 'Ap,Target', 'Ap,TargetType', 'ApBoardID', 'ApChipID',
                         'ApSecurityDomain', 'BMU,BoardID', 'BMU,ChipID', 'BbChipID', 'BbProvisioningManifestKeyHash',
                         'BbActivationManifestKeyHash', 'BbCalibrationManifestKeyHash', 'Ap,ProductMarketingVersion',
                         'BbFactoryActivationManifestKeyHash', 'BbFDRSecurityKeyHash', 'BbSkeyId', 'SE,ChipID',
                         'Savage,ChipID', 'Savage,PatchEpoch', 'Yonkers,BoardID', 'Yonkers,ChipID',
                         'Yonkers,PatchEpoch', 'Rap,BoardID', 'Rap,ChipID', 'Rap,SecurityDomain', 'Baobab,BoardID',
                         'Baobab,ChipID', 'Baobab,ManifestEpoch', 'Baobab,SecurityDomain', 'eUICC,ChipID',
                         'PearlCertificationRootPub', 'Timer,BoardID,1', 'Timer,BoardID,2', 'Timer,ChipID,1',
                         'Timer,ChipID,2', 'Timer,SecurityDomain,1', 'Timer,SecurityDomain,2', 'Manifest',
                         ]
        else:
            key_list += additional_keys

        for k in key_list:
            try:
                v = self[k]
                if isinstance(v, str) and v.startswith('0x'):
                    v = int(v, 16)
                parameters[k] = v
            except KeyError:
                pass

        if additional_keys is None:
            # special treat for RequiresUIDMode
            info = self.get('Info')
            if info is None:
                return
            requires_uid_mode = info.get('RequiresUIDMode')
            if requires_uid_mode is not None:
                parameters['RequiresUIDMode'] = requires_uid_mode

    def extract_dsc(self, output: Path) -> None:
        build_identity = self.build_manifest.build_identities[0]
        if not build_identity.has_component('Cryptex1,SystemOS'):
            return

        device_support_symbols_path = output / 'private/preboot/Cryptexes/OS/System'
        device_support_symbols_path.mkdir(parents=True, exist_ok=True)

        _extract_dmg(build_identity.get_component('Cryptex1,SystemOS').data, device_support_symbols_path,
                     sub_path=Path('System'))
        _split_dsc(output)

    def extract(self, output: Path) -> None:
        logger.info(f'extracting into: {output}')

        build_identity = self.build_manifest.build_identities[0]

        logger.info(f'extracting OS into: {output}')
        _extract_dmg(build_identity.get_component('OS').data, output)

        kernel_component = build_identity.get_component('KernelCache')
        kernel_path = Path(kernel_component.path)
        kernel_output = output / 'System/Library/Caches/com.apple.kernelcaches' / kernel_path.parts[-1]

        logger.info(f'extracting kernel into: {kernel_output}')
        kernel_output.write_bytes(kernel_component.data)

        for cryptex in ('App', 'OS'):
            name = {
                'App': 'Cryptex1,AppOS',
                'OS': 'Cryptex1,SystemOS',
            }[cryptex]

            if not build_identity.has_component(name):
                continue

            cryptex_path = output / 'private/preboot/Cryptexes' / cryptex
            cryptex_path.mkdir(parents=True, exist_ok=True)

            logger.info(f'extracting {name} into: {cryptex_path}')
            _extract_dmg(build_identity.get_component(name).data, cryptex_path)

        _split_dsc(output)
