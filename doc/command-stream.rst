.. _stream:

``stream``
==========

This command is the sister of ``carml circ``, allowing you to view and play with streams.

Currently, you can do one of three things:

 * ``--list`` (``-L``) shows you all current streams
 * ``--attach`` (``-a``) forces all subsequent streams to attach to a particular circuit-id (until you exit carml with Control-C)
 * ``--close`` (``-d``) close a stream


Examples
--------

.. sourcecode::
   console

   $ carml circ -L
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   Circuits:
      974: BUILT 14 minutes ago carmlfake0->fluxe4->~TorLand1
      975: BUILT 14 minutes ago carmlfake1->bethesdatech->Dontbleed2
   $ carml stream --attach 975
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   Exiting (e.g. Ctrl-C) will cause Tor to resume choosing circuits.
   Attaching all new streams to Circuit 975.
       carmlfake1->bethesdatech->Dontbleed2
     attaching 1719 (resolve encrypted.google.com)
     attaching 1720 encrypted.google.com:443
   ^C
   $ 
