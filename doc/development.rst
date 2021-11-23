Development
===========

Making a Release
----------------

* Bump library dependencies: make freeze
* Update version in:
 - Makefile (near top)
 - setup.py
 - doc/conf.py (two places)
* Unlock GPG (e.g. decrypt something)
* Try out the release: make release
* Satisfied? Upload:
 - pip install twine
 - make release-upload
