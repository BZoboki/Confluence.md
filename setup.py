"""Setup configuration for Confluence.md - Confluence to Markdown exporter."""
from setuptools import setup, find_packages
from pathlib import Path

# Read requirements from requirements.txt
requirements_path = Path(__file__).parent / 'requirements.txt'
with open(requirements_path, 'r', encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='confluence-md',
    version='0.1.0',
    description='CLI tool to export Confluence pages to Markdown files',
    author='Confluence.md Contributors',
    author_email='',
    url='https://github.com/bzoboki/Confluence.md',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'confluence-md=confluence_md.cli:main',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
