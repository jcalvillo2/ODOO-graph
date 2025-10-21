"""
Setup script para Odoo Dependency Tracker.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="odoo-dependency-tracker",
    version="0.1.0",
    author="Odoo Dependency Tracker Team",
    description="Herramienta para analizar y visualizar dependencias de módulos Odoo",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/odoo-dependency-tracker",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        "neo4j>=5.14.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "odoo-tracker=src.cli:cli",
        ],
    },
)
