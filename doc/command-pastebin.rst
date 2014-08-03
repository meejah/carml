.. _pastebin:

``pastebin``
============

This launches a new hidden-service to share some data as the
``text/plain`` MIME type via a Twisted Web server. By default, the
data to share is read from stdin. You may also use the option
``--file`` (``-f``) to share a single file instead.

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
