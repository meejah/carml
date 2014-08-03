.. _newid:

``newid``
=========

This basically just runs ``signal newnym`` (which you could do with
:ref:`cmd` of course) but also verifies that Tor actually does give
you a new identity (which can fail, as this command is rate-limited).

Usage is simple:

.. sourcecode::
   console

   $ carml newid
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   Requesting new identity
   success.

