.. _onion:

``onion``
========

This command starts an Onion Service on the connected Tor whose
livetime is tied to this process (when `carml onion` exits, the Onion
Service will be removed from Tor).

You may forward more than one port which might be useful for e.g. an
HTTP and Git server on the same Onion address. The "local" portion may
include an IP address and port or a unix-domain socket.


Examples
--------

Forward both "80" and "9418" on a version 3 service. This will forward
an incoming request on port 80 to 127.0.0.1:80 (and 9418 to
127.0.0.1:9418) and is the simplest way to set up a service::

    carml onion --port 80 --port 9418


If you are running the other services in containers or similar,
perhaps they are on different (but still local) IP addresses. Note
that we're also forward "80" to "8888" here, which is fine::

    carml onion --port 80:192.168.0.123:8888 --port 9418:192.168.0.123:9418


You may also run services via unix sockets. If your other services are
on the same machine, this is the safest and fastest way to forward::

    carml onion --port 80:unix:/var/run/nginx_sock --port 9418:unix:/var/run/git_sock
