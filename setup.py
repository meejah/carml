import sys
import os
import shutil
import re
from setuptools import setup, find_packages


__version__ = '16.3.0'


setup(
    name='carml',
    version=__version__,
    author='meejah',
    author_email='meejah@meejah.ca',
    url='https://github.com/meejah/carml',
    license='Public Domain (http://unlicense.org/)',
    description='A command-line tool to query and control a running Tor. Based on txtorcon + Twisted.',
    long_description=open('README.rst', 'r').read(),
    keywords=['python', 'twisted', 'tor', 'command-line', 'cli'],
    install_requires=[
        'humanize',
        'ansicolors',
        'backports.lzma',
        'txtorcon>=0.14.0',
        'txsocksx>=1.15.0.2',
    ],
    classifiers=[
        'Framework :: Twisted',
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: System :: Networking',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Internet',
        'Topic :: Security',
        'Topic :: Utilities'],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'carml = carml.dispatch:dispatch'
        ]
    },
    include_package_data=True,
    package_data={'': ['*.asc', '*.pem']},
    data_files=[
        ('share/carml', ['README.rst', 'meejah.asc']),
        ('share/carml/doc/', ['doc/' + x for x in filter(lambda x: x.endswith('.rst'), os.listdir('doc'))]),
        ('share/carml/example_extension/carml/command', ['example_extension/carml/command/blam.py']),
    ]
)
