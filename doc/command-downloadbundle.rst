.. _downloadbundle:

``downloadbundle``
==================

.. note::

   This command requires the optional `txsocksx
   <https://github.com/habnabit/txsocksx>`_ library to be
   installed. Simply a ``pip install txsocksx``

The ``downloadbundle`` command figures out what the latest Tor Browser
Bundle is (from check.torproject.org), downloads the package for your
operating system and (optionally) extracts it. It has bundled
certificates for torproject.org and **checks that the public keys** are
the same. It also **checks the signature** on the downloaded bundle, using
bundled keys for Tor people or (optionally) the current user's GnuPG
keychain.

To use your own keychain, use ``--system-keychain`` (``-K``). By
default, the command builds a tempdir for GnuPG and imports the
bundled keys (of Tor people who typically sign the release) there.

Use ``--beta`` (``-b``) to download the latest Beta release instead
(if available).

Use ``--no-extract`` (``-E``) if you do not wish to extract the bundle
after downloading. You additionally need ``backports.lzma`` installed
for this to work.

If you're really feeling adventurous, don't have a system Tor running,
or can't install ``txsocksx`` for some reason, you can (completely
inadvisably) pass ``--use-clearnet`` to download over the plain
Internet. Of course, you still get the certificate pins and signature
checking.



Examples
--------

.. sourcecode::
   console

   $ carml downloadbundle -e
   Getting recommended versions from "https://check.torproject.org/RecommendedTBBVersions".
      3.6-Linux, 3.6-MacOS, 3.6-Windows, 3.6.1-Linux, 3.6.1-MacOS,
      3.6.1-Windows
   tor-browser-linux64-3.6.1_en-US.tar.xz.asc: already exists, so not downloading.
   tor-browser-linux64-3.6.1_en-US.tar.xz: already exists, so not downloading.
   gpg: Signature made Tue 06 May 2014 05:37:07 PM MDT using RSA key ID 63FEE659
   gpg: Good signature from "Erinn Clark <erinn@torproject.org>"
   gpg:                 aka "Erinn Clark <erinn@debian.org>"
   gpg:                 aka "Erinn Clark <erinn@double-helix.org>"
   gpg: WARNING: This key is not certified with a trusted signature!
   gpg:          There is no indication that the signature belongs to the owner.
   Primary key fingerprint: 8738 A680 B84B 3031 A630  F2DB 416F 0610 63FE E659
   Signature is good.
   Extracting "tor-browser-linux64-3.6.1_en-US.tar.xz"...
     decompressing...
      20% extracted
      40% extracted
      60% extracted
      80% extracted
     100% extracted
   Tor Browser Bundle downloaded and extracted.
   To run:
      ./tor-browser_en-US/start-tor-browser


Note that for users who have a valid trust-path to Erinn Clark, using
``--system-keychain`` would avoid the WARNING: from GnuPG.
