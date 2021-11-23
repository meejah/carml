import sys
import os
import shutil
import re
from setuptools import setup, find_packages


__version__ = '21.0.0'


if True:
    with open('requirements-pinned.txt', 'r') as f:
        requires = f.readlines()
else:
    # you may like to do this for local / dev usage to get latest
    # versions, etc.
    with open('requirements-min.txt', 'r') as f:
        requires = f.readlines()


setup(
    name='carml',
    version=__version__,
    author='meejah',
    author_email='meejah@meejah.ca',
    url='https://github.com/meejah/carml',
    license='Public Domain (http://unlicense.org/)',
    description='A command-line tool to query and control a running Tor. Based on txtorcon + Twisted.',
    long_description=open('README.rst', 'r').read(),
##    long_description_type='rst',
    keywords=['python', 'twisted', 'tor', 'command-line', 'cli'],
    install_requires=requires,
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
        'Programming Language :: Python :: 3',
        'Topic :: System :: Networking',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Internet',
        'Topic :: Security',
        'Topic :: Utilities'],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'carml = carml.cli:carml'
        ]
    },
    include_package_data=True,
    package_data={'': ['*.asc', '*.pem']},
    data_files=[
        ('share/carml', ['README.rst', 'meejah.asc']),
        ('share/carml/doc/', ['doc/' + x for x in filter(lambda x: x.endswith('.rst'), os.listdir('doc'))]),
    ]
)
