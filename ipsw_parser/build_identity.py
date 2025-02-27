import logging
import shutil
from collections import UserDict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import requests
from cached_property import cached_property
from plumbum import ProcessExecutionError, local
from pyimg4 import IM4P

from ipsw_parser.component import Component

logger = logging.getLogger(__name__)


def _extract_dmg(buf: bytes, output: Path, sub_path: Optional[Path] = None, pem_db: Optional[str] = None) -> None:
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
            args = ['fw', 'aea', dmg_aea, '-o', temp_dir]
            if pem_db is not None:
                if '://' in pem_db:
                    # create a local file containing it
                    temp_pem_db = temp_dir / 'pem-db.json'
                    temp_pem_db.write_text(requests.get(pem_db, verify=False).text)
                    pem_db = temp_pem_db
                args += ['--pem-db', pem_db]
            ipsw(args)
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
    def manifest(self) -> dict:
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

    def extract_dsc(self, output: Path, pem_db: Optional[str] = None) -> None:
        build_identity = self.build_manifest.build_identities[0]
        if not build_identity.has_component('Cryptex1,SystemOS'):
            return

        device_support_symbols_path = output / 'private/preboot/Cryptexes/OS/System'
        device_support_symbols_path.mkdir(parents=True, exist_ok=True)

        _extract_dmg(build_identity.get_component('Cryptex1,SystemOS').data, device_support_symbols_path,
                     sub_path=Path('System'), pem_db=pem_db)
        _split_dsc(output)

    def get_kernelcache_payload(self, arch: Optional[str] = None) -> bytes:
        im4p = IM4P(self.build_manifest.build_identities[0].get_component('KernelCache').data)
        im4p.payload.decompress()
        payload = im4p.payload.output().data
        if arch is None:
            return payload

        with TemporaryDirectory() as temp_dir:
            kernel_output = Path(temp_dir) / 'kernel'
            local['ipsw']('macho', 'lipo', '-a', arch, kernel_output)
            return Path(next(kernel_output.parent.glob(f'*.{arch}'))).read_bytes()

    def extract(self, output: Path, pem_db: Optional[str] = None) -> None:
        logger.info(f'extracting into: {output}')

        build_identity = self.build_manifest.build_identities[0]

        logger.info(f'extracting OS into: {output}')
        _extract_dmg(build_identity.get_component('OS').data, output, pem_db=pem_db)

        kernel_component = build_identity.get_component('KernelCache')
        kernel_path = Path(kernel_component.path)
        kernel_output = output / 'System/Library/Caches/com.apple.kernelcaches' / kernel_path.parts[-1]

        logger.info(f'extracting kernel into: {kernel_output}')
        im4p = IM4P(kernel_component.data)
        im4p.payload.decompress()
        kernel_output.write_bytes(im4p.payload.output().data)
        try:
            # In case the kernel is a FAT image, extract the arm64 macho
            local['ipsw']('macho', 'lipo', '-a', 'arm64', kernel_output)
            list(kernel_output.parent.glob('*.arm64'))[0].rename(kernel_output)
        except ProcessExecutionError:
            pass

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
            _extract_dmg(build_identity.get_component(name).data, cryptex_path, pem_db=pem_db)

        _split_dsc(output)
