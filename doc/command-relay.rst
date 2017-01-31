.. _relay:

``relay``
==========

List and find relays. These are based on the current notion of the
consensus that the Tor we've connected to has. This comes from
"microdescriptors" that Tor downloads from Directory Authorities
periodically.

Relays are usually referred to by their "hex ID", a 40-character
representation of the actual (binary) relay ID which itself is a hash
of the relay's public identity key.

Use ``carml relay --info`` to search for a relay by key-ID or its name
(or a subset thereof) and print some information about the relay (or
relays) found.

Sometimes relays can come and go; if you want to wait for a relay with
a particular hex-ID to be in the consensus, use ``carml relay --await
hex_id``. This will either work immediately (if the relay is already
in the consensus) or wait for ``NEWCONSENSUS`` events to see if the
relay has appeared yet.


Examples
--------

.. sourcecode::
   console

   $ carml relay --list | wc -l
   7197
   $ carml relay --info [hex id]
        name: [redacted]
      hex id: $[redacted]
    location: XX
     address: [redacted]:9011 (DirPort=9030)
    last published 28 days ago
