.. _pastebin:

``pastebin``
============

This launches a new hidden-service to share some data as the
``text/plain`` MIME type via a Twisted Web server. By default, the
data to share is read from stdin. You may also use the option
``--file`` (``-f``) to share a single file instead.

To use stealth authentication on your hidden-service, you can pass the
``--keys`` (``-k``) option which specifies how many authentication
cookies to create. This will print out the commands you can send
(**securely**!) to the people you want to share
with.

If you wish to serve an entire hierarchy of files as a Web site,
instead see instructions at `txtorcon
<https://txtorcon.readthedocs.org/en/latest/howtos.html#endpoints-enable-tor-with-any-twisted-service>`_
(would look like ``twistd web --port "onion:80" --path ~/public_html``
with txtorcon installed).

A similar alternative is also `onionshare <https://onionshare.org/>`_
for diverse file-types on many OSes. OnionShare also comes with a GUI.

.. note::

    Note that the hidden-service private keys are in a freshly created
    temporary directory (``TMPDIR`` is honoured) and that you must
    **save them yourself (by copying them somewhere)** before you end (e.g
    with Control-C) the ``carml pastebin`` command, which deletes the
    tempdir (including the new keys).

If you want to see what it will look like to the people you're sharing
the link with, use ``--dry-run`` (``-d``) which starts a local
listener only (i.e. doesn't launch a Tor, nor set up an actual hidden
service). This is preferable to actually-launching a service just to
test it.


Examples
--------

.. sourcecode:: shell-session

    $ export TMPDIR=/dev/shm
    $ echo "hello hidden-serice world" | carml pastebin
    25 bytes to share.
    Launching Tor: connected.
    People using Tor Browser Bundle can find your paste at (once the descriptor uploads):

       http://ok2byooigb4v53be.onion

    If you wish to keep the hidden-service keys, they're in (until we shut down):
    /dev/shm/tortmp6eHPg4
    Awaiting descriptor upload...
    Descriptor uploaded; hidden-service should be reachable.
    Mon Jul 21 13:54:38 2014: Serving request to User-Agent "curl/7.37.0".
    ^CShutting down.
    $

If you used the stealth-authentication version, it might look like this:

.. sourcecode:: shell-session

    $ carml pastebin -f README.rst --keys 5
    4573 bytes to share with 5 authenticated clients.
    Launching Tor.
    [▋         ] Connecting to directory server
    [█▏        ] Finishing handshake with directory server
    [█▋        ] Establishing an encrypted directory connection
    [██▏       ] Asking for networkstatus consensus
    ...
    [███████▊  ] Loading relay descriptors
    [███████▉  ] Loading relay descriptors
    [████████▏ ] Connecting to the Tor network
    [█████████▏] Establishing a Tor circuit
    [██████████] Done
    [██████████] Waiting for descriptor upload...
    [██████████] At least one descriptor uploaded.
    You requested stealth authentication.
    Tor has created 5 keys; each key should be given to one person.
    They can set one using the "HidServAuth" torrc option, like so:

      HidServAuth ww2ufwkgxb2kag6t.onion ErQPDEHdNNprvWYCA2vTLR
      HidServAuth f5kb64pe3nygyplx.onion HeemYe0TIoOzU/WkjJwP3R
      HidServAuth ywhbfzepvss5hecm.onion 8JcZKcS8YQXMuYBF/G1z8x
      HidServAuth pow2d55j6ezrruib.onion jK6/yXZ2R7xDsf3sm/PyVh
      HidServAuth t7gnlwzw4hjxc45z.onion ezUZBaPmFYSzrGeZXYJfGh

    Alternatively, any Twisted endpoint-aware client can be given
    the following string as an endpoint:

      tor:ww2ufwkgxb2kag6t.onion:authCookie=ErQPDEHdNNprvWYCA2vTLR
      tor:f5kb64pe3nygyplx.onion:authCookie=HeemYe0TIoOzU/WkjJwP3R
      tor:ywhbfzepvss5hecm.onion:authCookie=8JcZKcS8YQXMuYBF/G1z8x
      tor:pow2d55j6ezrruib.onion:authCookie=jK6/yXZ2R7xDsf3sm/PyVh
      tor:t7gnlwzw4hjxc45z.onion:authCookie=ezUZBaPmFYSzrGeZXYJfGh

    For example, using carml:

      carml copybin --onion tor:ww2ufwkgxb2kag6t.onion:authCookie=ErQPDEHdNNprvWYCA2vTLR
      carml copybin --onion tor:f5kb64pe3nygyplx.onion:authCookie=HeemYe0TIoOzU/WkjJwP3R
      carml copybin --onion tor:ywhbfzepvss5hecm.onion:authCookie=8JcZKcS8YQXMuYBF/G1z8x
      carml copybin --onion tor:pow2d55j6ezrruib.onion:authCookie=jK6/yXZ2R7xDsf3sm/PyVh
      carml copybin --onion tor:t7gnlwzw4hjxc45z.onion:authCookie=ezUZBaPmFYSzrGeZXYJfGh
