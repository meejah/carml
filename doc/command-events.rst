.. _events:

``events``
==========

Simplistic interaction with Tor's "Events". This simply subscribes to
the event(s) you list, and prints out the text Tor sends back.

If you only want to listen for a certain number of events, use
``--count`` (``-n``) with an argument or the special-case ``--once``
for a single event. This might be useful, for example, to determine
when your Tor downloads a new consensus (like the first example, but
use NEWCONSENSUS instead).

Note that the count of events is global; if you listen for 2 different
events with ``--once``, the command will exit after the first event
(i.e. not one of each).


Examples
--------

.. sourcecode::
   console

   $ carml -q events --once ADDRMAP
   carml.readthedocs.org 162.209.114.75 "2014-06-04 23:47:37" EXPIRES="2014-06-05 05:47:37" CACHED="YES"   
   $ carml events --count 5 INFO
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   exit circ (length 3): carmlfake0(open) carmlfake1(open) $AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA(open) 
   pathbias_count_use_attempt(): Used circuit 982 is already in path state use succeeded. Circuit is a General-purpose client currently open. 
   link_apconn_to_circ(): Looks like completed circuit to [scrubbed] does allow optimistic data for connection to [scrubbed] 
   connection_ap_handshake_send_resolve(): Address sent for resolve, ap socket 14, n_circ_id 2147503826 
   connection_edge_process_inbuf(): data from edge while in 'waiting for resolve response' state. Leaving it on buffer.
