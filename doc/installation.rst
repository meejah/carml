Installing carml
----------------

The only supported way to install this currently is via ``pip``::

   pip install carml

This will install the dependencies, which are:

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

If you changed tor's configuration, don't forget to tell it (as
root):

.. code-block:: console

    # service tor reload
