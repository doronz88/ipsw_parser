#!/usr/bin/env python3
import click
import coloredlogs
import logging

from ipsw_parser.ipsw import IPSW

coloredlogs.install(level=logging.INFO)

logging.getLogger('asyncio').disabled = True
logging.getLogger('parso.cache').disabled = True
logging.getLogger('parso.cache.pickle').disabled = True
logging.getLogger('parso.python.diff').disabled = True
logging.getLogger('humanfriendly.prompts').disabled = True
logging.getLogger('blib2to3.pgen2.driver').disabled = True
logging.getLogger('urllib3.connectionpool').disabled = True

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command('parse')
@click.argument('file', type=click.File('rb'))
def parse(file):
    ipsw = IPSW(file)
    print(ipsw.build_manifest)


if __name__ == '__main__':
    cli()
