#!/usr/bin/env python

from setuptools import setup
import versioneer

setup(
    name="scalable",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Assist with orchestrating containers on job queing systems like Slurm",
    url="https://github.com/JGCRI/scalable",
    python_requires=">=3.8",
    license="BSD-2-Clause",
    packages=["scalable"],
    include_package_data=True,
    tests_require=["pytest >= 2.7.1"],
    zip_safe=False,
)
