.. _cmd:

``cmd``
=======

The command named ``cmd`` takes the rest of the command-line and sends
it straight to Tor as a control-protocol request (see `the torspec
repository <https://gitweb.torproject.org/torspec.git>`_ for full
details). It then prints out the reply from Tor. (This isn't really
suitable for events; see the ``events`` command).

If you pass a single dash as the command-line (that is, ``carml cmd
-``) then commands are read one line at a time from stdin and executed
sequentially.

Examples
--------

.. sourcecode::
   console

   $ carml -q cmd getinfo info/names | tail -5
   status/version/recommended -- List of currently recommended versions.
   stream-status -- List of current streams.
   traffic/read -- Bytes read since the process was started.
   traffic/written -- Bytes written since the process was started.
   version -- The current version of Tor.

   $ carml -q cmd SIGNAL NEWNYM
   OK

   $ echo "getinfo net/listeners/socks" > commands
   $ echo "getinfo traffic/read" >> commands
   $ echo "getinfo traffic/written" >> commands
   $ cat commands | carml -q cmd -
   Keep entering keys to run CMD on. Control-d to exit.
   net/listeners/socks="127.0.0.1:9050"
   traffic/read=6667674
   traffic/written=391959

   $ carml -q cmd getinfo net/listeners/socks traffic/read traffic/written
   net/listeners/socks="127.0.0.1:9050"
   traffic/read=10012841
   traffic/written=516428
