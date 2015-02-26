General Options
===============

The ``carml`` command itself takes a few options that are common to
all sub-commands.

``--connect, -c``
-----------------

How to connect to Tor. This accepts a Twisted `endpoint client string
<http://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.clientFromString.html>`_
as well as just a port. The default is ``localhost:9151`` (`Tor
Browser Bundle <https://www.torproject.org/download/download-easy.html.en>`_
default). Some examples:

.. sourcecode:: shell-session

 $ carml --connect 9151
 $ carml --connect 127.0.0.1:9051
 $ carml --connect tcp:port=9051:host=127.0.0.1

If you use password authentication, you can supply one with
``--password`` or ``-p``. If you're on the same machine, use cookie
authentication instead.


``--quiet, -q``
---------------

As little output as possible on standard out. Warnings may still be
printed on standard error.


``--info, -i``
--------------

Print Tor version when we connect, and whether it is dormant or not.


``--color, C``
--------------

Whether to output colors or not. Can be ``auto`` (the default), ``no``
or ``always``. You can also use the separate option ``--no-color``
which is the same as ``--color=no``


``--timestamps, -t``
--------------------

Prepend messages with a timestamp.


``--debug, -d``
---------------

If there's an error, print the stack trace out along with the error
message; could be useful for bug-reports and development.


The Subcommands
===============

Similar to programs like ``git``, the real functionality of carml is
in the sub-commands. They all take their own options (but obey global
options listed above). You can get any help on a command with the
``help`` subcommand, like: ``carml help subcommand``

.. toctree::
   :maxdepth: 1

   command-pastebin
   command-copybin
   command-downloadbundle
   command-monitor
   command-stream
   command-xplanet
   command-cmd
   command-circ
   command-newid
   command-events

