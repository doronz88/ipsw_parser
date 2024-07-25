#!/usr/bin/env python3
import logging
import plistlib
from datetime import datetime
from pathlib import Path
from typing import IO
from zipfile import ZipFile

import click
import coloredlogs

from ipsw_parser.ipsw import IPSW

coloredlogs.install(level=logging.DEBUG)

logging.getLogger('asyncio').disabled = True
logging.getLogger('parso.cache').disabled = True
logging.getLogger('parso.cache.pickle').disabled = True
logging.getLogger('parso.python.diff').disabled = True
logging.getLogger('humanfriendly.prompts').disabled = True
logging.getLogger('blib2to3.pgen2.driver').disabled = True
logging.getLogger('urllib3.connectionpool').disabled = True

logger = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    """ CLI utility for extracting info from IPSW files """
    pass


@cli.command('info')
@click.argument('file', type=click.Path(exists=True, file_okay=True, dir_okay=False))
def info(file) -> None:
    """ Parse given .ipsw basic info """
    ipsw = IPSW(ZipFile(file))
    print(f'SupportedProductTypes: {ipsw.build_manifest.supported_product_types}')
    print(f'ProductVersion: {ipsw.build_manifest.product_version}')
    print(f'ProductBuildVersion: {ipsw.build_manifest.product_build_version}')

    development_files = ipsw.get_development_files()
    if development_files:
        print('DevelopmentFiles:')
        for file in development_files:
            print(f'- {file}')


@cli.command('extract')
@click.argument('file', type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument('output', type=click.Path(exists=False))
def extract(file: IO, output: str) -> None:
    """ Extract .ipsw into filesystem layout """
    output = Path(output)

    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)

    ipsw = IPSW(ZipFile(file))
    ipsw.build_manifest.build_identities[0].extract(output)
    ipsw.archive.extractall(
        path=output, members=[f for f in ipsw.archive.filelist if f.filename.startswith('Firmware')])


@cli.command('device-support')
@click.argument('file', type=click.Path(exists=True, file_okay=True, dir_okay=False))
def device_support(file: IO) -> None:
    """ Create DeviceSupport directory """
    device_support_path = Path('~/Library/Developer/Xcode/iOS DeviceSupport').expanduser()
    ipsw = IPSW(ZipFile(file))
    device_support_path /= (f'{ipsw.build_manifest.supported_product_types[0]} '
                            f'{ipsw.build_manifest.product_version} ({ipsw.build_manifest.product_build_version})')
    build_identity = ipsw.build_manifest.build_identities[0]
    symbols_path = device_support_path / 'Symbols'
    build_identity.extract_dsc(symbols_path)
    for file in (symbols_path / 'private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld').iterdir():
        file.unlink()
    (device_support_path / 'Info.plist').write_bytes(plistlib.dumps({
        'DSC Extractor Version': '1228.0.0.0.0',
        'DateCollected': datetime.now(),
        'Version': '16.0',
    }))
    (device_support_path / '.finalized').write_bytes(plistlib.dumps({}))
    (device_support_path / '.processed_dyld_shared_cache_arm64e').touch()
    (device_support_path / '.processing_lock').touch()


if __name__ == '__main__':
    cli()
