[![Python application](https://github.com/doronz88/ipsw_parser/workflows/Python%20application/badge.svg)](https://github.com/doronz88/ipsw_parser/actions/workflows/python-app.yml "Python application action")
[![Pypi version](https://img.shields.io/pypi/v/ipsw_parser.svg)](https://pypi.org/project/ipsw_parser/ "PyPi package")
[![Downloads](https://static.pepy.tech/personalized-badge/ipsw_parser?period=total&units=none&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/ipsw_parser)

# Overview

python3 utility for parsing and extracting data from IPSW.

# Installation

```shell
python3 -m pip install ipsw-parser
```

Additionally, if you installed [blacktop/ipsw](https://github.com/blacktop/ipsw), the IPSW extraction will also contain
the split DSC.

# Usage

```
Usage: ipsw-parser [OPTIONS] COMMAND [ARGS]...

  CLI utility for extracting info from IPSW files

Options:
  --help  Show this message and exit.

Commands:
  device-support  Create DeviceSupport directory
  extract         Extract .ipsw into filesystem layout
  info            Parse given .ipsw basic info
```
