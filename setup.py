#!/usr/bin/env python3
"""
Setup script for franklinwh-modbus

Note: Both the distribution name and the Python import use 'franklinwh_modbus'
(pip install franklinwh-modbus, from franklinwh_modbus import ...).
The 'franklinwh' namespace is reserved for the Cloud API package (franklinwh-python).
"""

from setuptools import setup, find_packages
import os

# Read README if it exists
readme_path = os.path.join(os.path.dirname(__file__), 'readme.md')
long_description = ''
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()

setup(
    name='franklinwh-modbus',
    version='0.9.0',
    description='FranklinWH aGate Modbus TCP library — SunSpec + extension registers',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='David Hona',
    author_email='david2069@users.noreply.github.com',
    url='https://github.com/david2069/franklinwh-modbus',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    py_modules=['franklinwh_cli'],
    entry_points={
        'console_scripts': [
            'franklinwh=franklinwh_cli:main',
        ],
    },
    install_requires=[
        'pysunspec2>=1.1.0',
        'pymodbus>=3.0.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-mock>=3.0.0',
        ],
        'monitor': [
            'rich>=13.0.0',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Home Automation',
        'Topic :: System :: Hardware',
    ],
    keywords='franklinwh battery modbus sunspec energy solar',
)
