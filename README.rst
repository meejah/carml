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

**Documentation at:** `carml.rtfd.org <https://carml.readthedocs.org/en/latest/>`_ or `carmlion6vt4az2q.onion/ <http://carmlion6vt4az2q.onion/>`_
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
    (venv3)meejah@machine:~$ carml tbb
    Getting recommended versions from "http://expyuzz4wqqyqhjn.onion/projects/torbrowser/RecommendedTBBVersions".
       7.5.5, 7.5.5-MacOS, 7.5.5-Linux, 7.5.5-Windows, 7.5.6, 7.5.6-MacOS,
       7.5.6-Linux, 7.5.6-Windows, 8.0a8, 8.0a8-MacOS, 8.0a8-Linux,
       8.0a8-Windows, 8.0a9, 8.0a9-MacOS, 8.0a9-Linux, 8.0a9-Windows
    Note: there are alpha versions available; use --alpha to download.
    Downloading "tor-browser-linux64-7.5.5_en-US.tar.xz.asc" from:
       http://rqef5a5mebgq46y5.onion/torbrowser/7.5.5/tor-browser-linux64-7.5.5_en-US.tar.xz.asc
    Downloading "tor-browser-linux64-7.5.5_en-US.tar.xz" from:
       http://rqef5a5mebgq46y5.onion/torbrowser/7.5.5/tor-browser-linux64-7.5.5_en-US.tar.xz
    [▏    ] - 0.0 of 65.8 MiB (1s remaining)
    [▋    ] - 6.6 of 65.8 MiB (153s remaining)
    [█▏   ] - 13.2 of 65.8 MiB (137s remaining)
    [█▋   ] - 19.8 of 65.8 MiB (120s remaining)
    [██▏  ] - 26.4 of 65.8 MiB (102s remaining)
    [██▋  ] - 32.9 of 65.8 MiB (85s remaining)
    [███▏ ] - 39.5 of 65.8 MiB (70s remaining)
    [███▋ ] - 46.1 of 65.8 MiB (55s remaining)
    [████▏] - 52.7 of 65.8 MiB (38s remaining)
    [████▋] - 59.3 of 65.8 MiB (19s remaining)
    [█████] - 65.8 of 65.8 MiB (0s remaining)
    0.32 MiB/s
    gpg: assuming signed data in 'tor-browser-linux64-7.5.5_en-US.tar.xz'
    gpg: Signature made Sat 09 Jun 2018 06:42:37 AM MDT
    gpg:                using RSA key D1483FA6C3C07136
    gpg: Good signature from "Tor Browser Developers (signing key) <torbrowser@torproject.org>" [unknown]
    gpg: WARNING: This key is not certified with a trusted signature!
    gpg:          There is no indication that the signature belongs to the owner.
    Primary key fingerprint: EF6E 286D DA85 EA2A 4BA7  DE68 4E2C 6E87 9329 8290
         Subkey fingerprint: A430 0A6B C93C 0877 A445  1486 D148 3FA6 C3C0 7136
    Signature is good.
    Extracting "tor-browser-linux64-7.5.5_en-US.tar.xz"...
      decompressing...
       20% extracted
       40% extracted
       60% extracted
       80% extracted
      100% extracted
    Tor Browser Bundle downloaded and extracted.
    running: ./tor-browser_en-US/Browser/start-tor-browser



License
-------

``carml`` is public domain. See `unlicense.org
<http://unlicense.org/>`_ for more information.
