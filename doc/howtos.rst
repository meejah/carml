HOWTOs
======

Pull-requests with other ideas or instructions are encouraged!

Ensure Your Relay Is In Consensus
---------------------------------

Let's say you wanted to ensure that your relay is in each consensus
that's published (and didn't wish to use the Tor Weather
web-service). You could use the :ref:`events` sub-command to wait for
a NEWCONSENSUS event and ``grep`` through it for your relay's
fingerprint.

.. source-code:: shell-session

   carml -q events 

Wrapping this in a ``while`` loop would make it run forever.

Alternatively, you could use a ``cron`` job to query 
