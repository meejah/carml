.. _checkpypi:

``checkpypi``
=============

This helps you check the hashes for a PyPI requirement, as verifiable by `peep <https://github.com/erikrose/peep>`_. This does the following:

1. download the JSON metadata from PyPI via a Tor circuit
2. selects the newest version (or what you ask for with `--revision`)
3. creates 3 separate circuits, and downloads the sdist `.tar.gz` file over each one
4. compares the hashes

If any of the hashes are different, it complains. Otherwise, it prints out what you should copy/paste into your `requirements.txt` file for use with peep.
