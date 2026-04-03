#!/usr/bin/env python3
"""
OmniNet Architecture Package
Sovereign: Justin Neal Thomas Conzet (G0 Prime Sovereign Architect)
Bitcoin Anchor: Block 941747
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="omninet-sovereign",
    version="5.0.0",
    author="Justin Neal Thomas Conzet",
    author_email="sovereign@omninet.architecture",
    description="OmniNet Architecture - Sovereign Intelligence Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Zygros/omninet-v4",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.18.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "omninet=omninet.cli:main",
        ],
    },
)
