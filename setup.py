from pathlib import Path

from setuptools import setup, find_packages

BASE_DIR = Path(__file__).parent.resolve(strict=True)
VERSION = '1.0.0'
PACKAGE_NAME = 'ipsw_parser'
PACKAGES = [p for p in find_packages() if not p.startswith('tests')]


def parse_requirements():
    reqs = []
    with open(BASE_DIR / 'requirements.txt', 'r') as fd:
        for line in fd.readlines():
            line = line.strip()
            if line:
                reqs.append(line)
    return reqs


def get_description():
    return (BASE_DIR / 'README.md').read_text()


if __name__ == '__main__':
    setup(
        version=VERSION,
        name=PACKAGE_NAME,
        description='python3 utility for parsing and extracting data from IPSW',
        long_description=get_description(),
        long_description_content_type='text/markdown',
        cmdclass={},
        packages=PACKAGES,
        author='DoronZ',
        author_email='doron88@gmail.com',
        license='GNU GENERAL PUBLIC LICENSE - Version 3, 29 June 2007',
        install_requires=parse_requirements(),
        entry_points={
            'console_scripts': ['ipsw_parser=ipsw_parser.__main__:cli',
                                ],
        },
        classifiers=[
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: 3.11',
        ],
        url='https://github.com/doronz88/ipsw_parser',
        project_urls={
            'ipsw_parser': 'https://github.com/doronz88/ipsw_parser'
        },
        tests_require=['pytest', ],
    )
