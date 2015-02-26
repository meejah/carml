.. _copybin:

``copybin``
===========

This command downloads the contents of a ``carml pastebin``.

Mostly it exists because there's not a good way to specify
stealth-authentication cookies to commands like ``curl`` or similar.

The only option is ``--service`` which is a Twisted endpoint string
describing the service. Note that the "tor:..." string can be used
with any Twisted program that uses client endpoint strings (see
`clientFromString
<http://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.html#clientFromString>`_).

This is **experimental**: you'll need to get a ``txtorcon`` from the
``stealth-authentication`` branch; ``pip install -e
git+https://github.com/meejah/txtorcon.git@stealth-authentication#egg=txtorcon``)

This will end up looking something like this:

.. sourcecode:: shell-session

   $ carml copybin -s tor:ccsq7wrrm2ejkhmg.onion:authCookie=POYAUUZf4O28iJM0ZpIiwx

