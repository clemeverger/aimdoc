#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="aimdoc",
    version="2.0.0",
    author="Clement Verger",
    author_email="",
    description="Smart Documentation Scraper for AI Development",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/clemeverger/aimdoc",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Documentation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "scrapy>=2.8.0",
        "beautifulsoup4>=4.11.0",
        "markdownify>=0.11.0",
        "lxml>=4.9.0",
        "requests>=2.28.0",
        "rich>=13.0.0",
        "typer>=0.9.0",
        "pydantic>=2.5.0",
    ],
    entry_points={
        "console_scripts": [
            "aimdoc=aimdoc.__main__:main",
        ],
    },
)