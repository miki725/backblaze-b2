#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os

from setuptools import find_packages, setup

from backblaze_b2 import __author__, __version__


def read(fname):
    try:
        with open(os.path.join(os.path.dirname(__file__), fname), 'rb') as fid:
            return fid.read().decode('utf-8')
    except IOError:
        return ''


authors = read('AUTHORS.rst')
history = read('HISTORY.rst').replace('.. :changelog:', '')
licence = read('LICENSE.rst')
readme = read('README.rst')

requirements = read('requirements.txt').splitlines() + [
    'setuptools',
]

test_requirements = (
    read('requirements.txt').splitlines() +
    read('requirements-dev.txt').splitlines()[1:]
)

setup(
    name='backblaze-b2',
    version=__version__,
    author=__author__,
    description='Backblaze B2 object storage unofficial Python library.',
    long_description='\n\n'.join([readme, history, authors, licence]),
    url='https://github.com/miki725/backblaze-b2',
    license='MIT',
    packages=find_packages(exclude=['test_project*', 'tests*']),
    install_requires=requirements,
    test_suite='tests',
    tests_require=test_requirements,
    keywords=' '.join([
        'backblaze',
        'b2',
        'object storage',
    ]),
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Development Status :: 2 - Pre-Alpha',
    ],
)
