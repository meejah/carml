import sys
import os
import shutil
import re
from setuptools import setup, find_packages

__version__ = '0.0.6'
__author__ = 'meejah'
__contact__ = 'meejah@meejah.ca'
__url__ = 'https://github.com/meejah/carml'
__license__ = 'Public Domain (http://unlicense.org/)'
__copyright__ = 'Copyright 2014'

def pip_to_requirements(s):
    """
    Change a PIP-style requirements.txt string into one suitable for setup.py
    """

    if s.startswith('#'):
        return ''
    m = re.match('(.*)([>=]=[.0-9]*).*', s)
    if m:
        return '%s (%s)' % (m.group(1), m.group(2))
    return s.strip()

setup(name = 'carml',
      version = __version__,
      description = 'A command-line tool to query and control a running Tor. Based on txtorcon + Twisted.',
      long_description = open('README.rst', 'r').read(),
      keywords = ['python', 'twisted', 'tor', 'command-line', 'cli'],
      ## way to have "development requirements"?
      requires = filter(len, map(pip_to_requirements, 
                                 open('requirements.txt').readlines())),
      ## FIXME is requires even doing anything? why is format
      ## apparently different for install_requires?
      install_requires = filter(lambda x: not x.startswith('#'), open('requirements.txt').readlines()),
      classifiers = ['Framework :: Twisted',
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
      author = __author__,
      author_email = __contact__,
      url = __url__,
      license = __license__,
      packages = find_packages(),
      entry_points={
          'console_scripts': [
              'carml = carml.dispatch:dispatch'
          ]
      },
      include_package_data = True,
      package_data={'': ['*.asc', '*.pem']},
      data_files=[('share/carml', ['README.rst', 'meejah.asc']),
                  ('share/carml/doc/', ['doc/' + x for x in filter(lambda x: x.endswith('.rst'), os.listdir('doc'))]),
                  ('share/carml/example_extension/carml/command', ['example_extension/carml/command/blam.py']),
              ]
  )
