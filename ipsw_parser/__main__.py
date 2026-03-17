#!/usr/bin/env python3
import logging
from pathlib import Path
from typing import Annotated, Optional

import coloredlogs
import typer

from ipsw_parser.ipsw import IPSW

coloredlogs.install(level=logging.DEBUG)

logging.getLogger("asyncio").disabled = True
logging.getLogger("parso.cache").disabled = True
logging.getLogger("parso.cache.pickle").disabled = True
logging.getLogger("parso.python.diff").disabled = True
logging.getLogger("humanfriendly.prompts").disabled = True
logging.getLogger("blib2to3.pgen2.driver").disabled = True
logging.getLogger("urllib3.connectionpool").disabled = True

logger = logging.getLogger(__name__)

PEM_DB_ENV_VAR = "IPSW_PARSER_PEM_DB"

cli = typer.Typer(
    help="CLI utility for extracting info from IPSW files",
)

IpswArgument = Annotated[str, typer.Argument(help="Path to an IPSW zip, extracted IPSW directory, or HTTP URL.")]
OutputArgument = Annotated[Path, typer.Argument(help="Output path.", exists=False)]
PemDbOption = Annotated[
    Optional[str],
    typer.Option(
        "--pem-db",
        envvar=PEM_DB_ENV_VAR,
        help="Path DB file url (can be either a filesystem path or an HTTP URL). "
        "Alternatively, use the IPSW_PARSER_PEM_DB envvar.",
    ),
]
ArchOption = Annotated[Optional[str], typer.Option(help="Arch name to extract using lipo")]


@cli.command("info")
def info(ipsw: IpswArgument) -> None:
    """Parse given .ipsw basic info"""
    parsed_ipsw = IPSW.create_from_path(ipsw)
    print(f"SupportedProductTypes: {parsed_ipsw.build_manifest.supported_product_types}")
    print(f"ProductVersion: {parsed_ipsw.build_manifest.product_version}")
    print(f"ProductBuildVersion: {parsed_ipsw.build_manifest.product_build_version}")

    development_files = parsed_ipsw.get_development_files()
    if development_files:
        print("DevelopmentFiles:")
        for file in development_files:
            print(f"- {file}")


@cli.command("extract")
def extract(ipsw: IpswArgument, output: OutputArgument, pem_db: PemDbOption = None) -> None:
    """Extract .ipsw into filesystem layout"""
    parsed_ipsw = IPSW.create_from_path(ipsw)

    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)

    parsed_ipsw.build_manifest.build_identities[0].extract(output, pem_db=pem_db)
    parsed_ipsw.archive.extractall(
        path=output, members=[f for f in parsed_ipsw.archive.filelist if f.filename.startswith("Firmware")]
    )


@cli.command("extract-kernel")
def extract_kernel(ipsw: IpswArgument, output: OutputArgument, arch: ArchOption = None) -> None:
    """Extract kernelcache from given .ipsw into given output filename"""
    parsed_ipsw = IPSW.create_from_path(ipsw)
    output.write_bytes(parsed_ipsw.build_manifest.build_identities[0].get_kernelcache_payload(arch=arch))


@cli.command("device-support")
def device_support(ipsw: IpswArgument, pem_db: PemDbOption = None) -> None:
    """Create DeviceSupport directory"""
    IPSW.create_from_path(ipsw).create_device_support(pem_db=pem_db)


if __name__ == "__main__":
    cli()
