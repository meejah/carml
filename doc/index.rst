.. carml documentation


.. toctree::
   :maxdepth: 2

.. note:: This code is intended as utilities mostly to help developers
          and Tor experts interact with their systems. Nobody has
          audited it for anonymitiy leaks (or worse). Use at your own
          risk.


carml
=====

``carml`` is a command-line tool to query and control a running Tor
(including Tor Browser Bundle). You can do things like:

 * list and remove streams and circuits;
 * monitor stream, circuit and address-map events;
 * watch for any Tor event and print it (or many) out;
 * monitor bandwidth;
 * run any Tor control-protocol command;
 * pipe through common Unix tools like ``grep``, ``less``, ``cut``, etcetera;
 * download TBB through Tor, with pinned certs and signature checking;
 * ...even spit out and run ``xplanet`` configs (with router/circuit markers)!

It is written in Python and uses Tor's control-port via the `txtorcon
library <https://txtorcon.readthedocs.org>`_.

**Documentation at:** `carml.rtfd.org <https://carml.readthedocs.org/en/latest/>`_
**Code at:** `github.com/meejah/carml <https://github.com/meejah/carml/>`_

In some ways, ``carml`` started as a dumping-ground for things I
happened to make Tor do at least once from Python code. Are there
things you wish you could easily make Tor do from the command-line?
File an enhancement bug at GitHub!

``carml`` is also easy to extend, even with system- or `virtualenv
<http://docs.python-guide.org/en/latest/dev/virtualenvs/>`_- installed
packages.

Feedback is appreciated -- pull-requests and bug-reports (including
feature enhancements) welcome `at GitHub
<https://github.com/meejah/carml>`_ or you can contact me in `#tor-dev
on OFTC <irc://irc.oftc.net/tor-dev>`_ or via *meejah at meejah dot
ca* with the public-key contained in the source.

**I'm happy to accept a new logo** if it is open-licensed somehow;
obviously I'm no logo-designer ;)


Some Quick Examples
-------------------

.. sourcecode:: shell-session

    (venv)meejah@machine:~$ carml circ --list
    Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
    Circuits:
       809: BUILT 29 minutes ago carmlfake0->~Unnamed->lobstertech
       810: BUILT 29 minutes ago ~carmelfake1->~toxiroxi->~SECxFreeBSD64
       811: BUILT 5 minutes ago carmelfake2->torpidsDEinterwerk->~rainbowwarrior
       813: BUILT 24 seconds ago carmlfake0->~arkhaios1->~IPredator
    (venv)meejah@machine:~$ carml circ --delete 810
    Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
    Deleting circuit "810"...
    ...circuit 172 gone.
    (venv)meejah@machine:~$ echo "hello world" | carml pastebin --once
    12 bytes to share.
    Launching Tor: connected.
    People using Tor Browser Bundle can find your paste at (once the descriptor uploads):

       http://ok2byooigb4v53be.onion

    If you wish to keep the hidden-service keys, they're in (until we shut down):
    /dev/shm/tortmp6eHPg4
    Awaiting descriptor upload...
    Descriptor uploaded; hidden-service should be reachable.
    Mon Jul 21 13:54:38 2014: Serving request to User-Agent "curl/7.37.0".
    Shutting down.
    (venv)meejah@machine:~$ carml downloadbundle --extract
    Getting recommended versions from "https://check.torproject.org/RecommendedTBBVersions".
       3.6.3-Linux, 3.6.3-MacOS, 3.6.3-Windows
    tor-browser-linux64-3.6.3_en-US.tar.xz.asc: already exists, so not downloading.
    tor-browser-linux64-3.6.3_en-US.tar.xz: already exists, so not downloading.
    gpg: Signature made Fri 25 Jul 2014 11:20:02 AM MDT using RSA key ID 63FEE659
    gpg: Good signature from "Erinn Clark <erinn@torproject.org>"
    gpg:                 aka "Erinn Clark <erinn@debian.org>"
    gpg:                 aka "Erinn Clark <erinn@double-helix.org>"
    gpg: WARNING: This key is not certified with a trusted signature!
    gpg:          There is no indication that the signature belongs to the owner.
    Primary key fingerprint: 8738 A680 B84B 3031 A630  F2DB 416F 0610 63FE E659
    Signature is good.
    Extracting "tor-browser-linux64-3.6.3_en-US.tar.xz"...
      decompressing...
       20% extracted
       40% extracted
       60% extracted
       80% extracted
      100% extracted
    Tor Browser Bundle downloaded and extracted.
    To run:
       ./tor-browser_en-US/start-tor-browser


License
-------

``carml`` is public domain. See `unlicense.org
<http://unlicense.org/>`_ for more information.

.. toctree::
   :maxdepth: 2

   installation
   commands
   development
   howtos
