#!/usr/bin/env python

from os.path import exists

import versioneer
from setuptools import setup

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

extras_require = {}

extras_require["test"] = [
    "pytest",
    "pytest-asyncio",
    "cryptography",
]

if exists("README.rst"):
    with open("README.rst") as f:
        long_description = f.read()
else:
    long_description = ""

setup(
    name="scalable",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Assist with running models on job queing systems like Slurm",
    url="https://www.pnnl.gov",
    python_requires=">=3.8",
    license="BSD-2-Clause",
    packages=["scalable"],
    scripts=["scalable_bootstrap.sh"],
    include_package_data=True,
    install_requires=install_requires,
    tests_require=["pytest >= 2.7.1"],
    extras_require=extras_require,
    long_description=long_description,
    zip_safe=False,
)
