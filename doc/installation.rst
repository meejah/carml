Installing carml
----------------

Note (for PyPI or development installs) you'll need to install
``libffi`` and ``liblzma`` development libraries. How to do this on
various architectures (please send missing ones!):

 * Debian + Ubuntu: ``apt-get install libffi-dev liblzma-dev``.


PyPI
====

Once you have libraries installed as above, you should be able to do a
simple ``pip install carml``. It's also possible to point to the
``.whl`` file (after signature verification).

To try without affecting system packages:

.. sourcecode:: shell-session

    virtualenv venv
    . ./venv/bin/activate
    pip install carml

To use ``peep`` to verify upstream libraries against my copies, you'll
have to clone the source; see below.


Development/Source
==================

From a fresh clone (``git clone https://github.com/meejah/carml.git``)
type ``make venv``. Then activate your new virtualenv with ``source
./venv/bin/activate`` and then ``pip install --editable .`` which
should install all the dependencies (listed in ``requirements.txt``).

To do this and use ``peep``, you need pip version 6.1.1. So, you you
can try something like this (from the root of a fresh clone):

.. sourcecode:: shell-session

   virtualenv venv
   . ./venv/bin/activate
   pip install --upgrade pip==6.1.1 peep
   peep install -r requirements.txt
   pip install --editable .

(If you want to ensure pip doesn't decide to download something in the
last step, add ``--proxy localhost:77777`` or similar nonesense
endpoint because ``--no-download`` is now deprecated it turns out)


The main dependencies are:

 * `txtorcon <https://txtorcon.readthedocs.org>`_
 * `humanize <https://github.com/jmoiron/humanize>`_
 * `ansicolors <https://github.com/verigak/colors/>`_
 * `PyOpenSSL <https://github.com/pyca/pyopenssl>`_

Optionally, to use the :ref:`downloadbundle` command via Tor, you
need:

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
