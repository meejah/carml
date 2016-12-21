import sys
import os
import shutil
import re
from setuptools import setup, find_packages

__version__ = '16.1.0'
__author__ = 'meejah'
__contact__ = 'meejah@meejah.ca'
__url__ = 'https://github.com/meejah/carml'
__license__ = 'Public Domain (http://unlicense.org/)'
__copyright__ = 'Copyright 2014 - 2016'


requirements = [line.strip() for line in open('requirements.txt').readlines() if not line.startswith('#') and not line.startswith('--') and line.strip()]
print "DING", requirements

setup(
    name='carml',
    version=__version__,
    description='A command-line tool to query and control a running Tor. Based on txtorcon + Twisted.',
    long_description=open('README.rst', 'r').read(),
    keywords=['python', 'twisted', 'tor', 'command-line', 'cli'],
    install_requires=requirements,
    dependency_links=[
        'git+https://github.com/meejah/txtorcon.git@7d96607b764d1ffe71bc7f5a022668292aef7c2a#egg=txtorcon'
    ],
    classifiers=[
        'Framework :: Twisted',
        'Development Status :: 2 - Pre-Alpha',
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
    author=__author__,
    author_email=__contact__,
    url=__url__,
    license=__license__,
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
