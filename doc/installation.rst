Installing carml
----------------

Note (for PyPI or development installs) you'll need to install
``libffi`` and ``liblzma`` development libraries. How to do this on
various architectures (please send missing ones!):

 * Debian + Ubuntu: ``apt-get install build-essential python3-dev python3-virtualenv libffi-dev liblzma-dev``.


PyPI
====

Once you have libraries installed as above, you should be able to do a
simple ``pip install carml``. It's also possible to point to the
``.whl`` file (e.g. after signature verification).

It is recommended to use ``virtualenv`` to use ``carml`` without
affecting system packages:

.. sourcecode:: shell-session

    python3 -m venv venv
    source ./venv/bin/activate
    python3 -m pip install carml


Signatures
==========

If you would like to check the signatures and dependencies, you will
need to:

 - download the ``.whl`` file from PyPI.
 - change the URL to download the signature (add ``.asc`` to the end)
 - confirm signature: ``gpg --verify carml-18.4.0-py3-none-any.whl.asc``
 - clone source code: ``git clone https://github.com/meejah/carml``
 - ``git tag --verify v18.4.0``
 - ``git checkout v18.4.0``
 - The file ``requirements.txt`` has hashes for all dependencies, at
   the same versions as pinned in the wheel (and is included in the
   signature just checked on the tag). So install the dependencies:
 - ``python3 -m pip install --require-hashes --requirements requirements.txt``
 - Then, install the wheel file (and just that):
 - ``python3 -m pip install --no-deps carml-18.4.0-py3-none-any.whl``

You now have exactly the bytes I intended to release for both
``carml`` itself and all its dependencies.

Note: a much easier and arguably better way to get this on Debian or
Ubuntu would be for someone to package it in Debian...


Development/Source
==================

From a fresh clone (``git clone https://github.com/meejah/carml.git``)
type ``make venv``. Then activate your new virtualenv with ``source
./venv/bin/activate`` and then ``python3 -m pip install --editable .`` which
should install all the dependencies (listed in ``requirements.txt``).

To do this and use ``peep``, you need pip version 6.1.1. So, you you
can try something like this (from the root of a fresh clone):

.. sourcecode:: shell-session

   virtualenv venv
   source ./venv/bin/activate
   python3 -m pip install --upgrade pip setuptools  # esp. for Debian
   python3 -m pip install --editable .

Dependencies:

 * `txtorcon <https://txtorcon.readthedocs.org>`_
 * `humanize <https://github.com/jmoiron/humanize>`_
 * `ansicolors <https://github.com/verigak/colors/>`_
 * `PyOpenSSL <https://github.com/pyca/pyopenssl>`_
 * `txsocksx <https://github.com/habnabit/txsocksx>`_
 * `backports.lzma <https://github.com/peterjc/backports.lzma>`_


Tor Setup
---------

For Tor setup, make sure you have at least the following in
``/etc/tor/torrc``:

.. code-block:: linux-config

    CookieAuthentication 1
    CookieAuthFileGroupReadable 1
    ControlPort 9051
    # corresponding carml option: "--connect tcp:127.0.0.1:9051"

Or, if you prefer Unix sockets (recommended):

.. code-block:: linux-config

    CookieAuthentication 1
    ControlSocketsGroupWritable 1
    ControlSocket /var/run/tor/control
    # corresponding carml option: "--connect unix:/var/run/tor/control"

The port or unix-socket can obviously be whatever; the above are Tor's
defaults on Debian. The Tor Browser Bundle defaults to using 9151 for
the control socket (and DOES use cookie authentication by default).

On Debian/Ubuntu you need to be part of the ``debian-tor`` group. To
check, type ``groups`` and verify ``debian-tor`` is on the list. If
not, add yourself (as root, do):

.. code-block:: console

    # usermod username --append --groups debian-tor

If you changed Tor's configuration, don't forget to tell it (as
root):

.. code-block:: console

    # service tor reload
