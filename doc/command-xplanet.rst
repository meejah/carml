``xplanet``
===========

This command spits out valid `xplanet
<http://xplanet.sourceforge.net/>`_ configuartion files for the
"marker" files. If you pass the ``--execute`` (``-x``) argument, a
tempdir is created with a top-level xplanet configuration and xplanet
is run against that (causing a map to appear on your root window).

You can use ``--all`` (``-A``) to output markers for ALL routers
(instead of just ones active for you right now). Note that the
position of many will overlap as we don't do anything smart when two
co-ordinates are identical.

xplanet can include an ``arc_file`` for drawing lines between
relays. With ``-x`` or ``-f`` this is used to draw links between
relays in a circuit. You can also use ``--arc-file`` (``-a``) if
you're not using ``-x`` or ``-f``.

.. warning::

   Obviously, this could easily leak some information about which
   relays and circuits you are currently using. Since your guard-nodes
   (first hop of a circuit) are long-lived, it's advisable to use this
   for entertainment purposes mainly, and clear your root window when
   done.


Examples
--------

.. sourcecode:: shell-session

   $ carml xplanet -f
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   3 (23%) routers with no geoip information.
   xplanet -num_times 1 -projection rectangular -config /tmp/tmp_32oE5/xplanet-config 
   <Circuit 977 BUILT [redacted IPs] for GENERAL>
   <Circuit 977 BUILT [redacted IPs] for GENERAL>
   4 (27%) routers with no geoip information.
   xplanet -num_times 1 -projection rectangular -config /tmp/tmp_32oE5/xplanet-config 
   <Circuit 978 BUILT [redacted IPs] for GENERAL>
   <Circuit 978 BUILT [redacted IPs] for GENERAL>
   5 (29%) routers with no geoip information.
   xplanet -num_times 1 -projection rectangular -config /tmp/tmp_32oE5/xplanet-config 
