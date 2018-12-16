import sys
import time
import functools
from os import mkdir
from tempfile import mkdtemp
from shutil import rmtree

import zope.interface
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet.endpoints import serverFromString, clientFromString
from twisted.web.http import HTTPChannel
from twisted.web.static import Data
from twisted.web.resource import Resource
from twisted.web.server import Site

from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint
from txtorcon import AuthBasic, AuthStealth


class _PasteBinHTTPChannel(HTTPChannel):
    def connectionMade(self):
        HTTPChannel.connectionMade(self)
        self.site._got_client()

    def connectionLost(self, reason):
        HTTPChannel.connectionLost(self, reason)
        self.site._lost_client()


class PasteBinSite(Site):
    """
    See https://github.com/habnabit/polecat/blob/master/polecat.py for
    the inspriation behind this.

    This class exists so we can count active connections and support a
    command-line option for serving a particular number of
    requests. We need to wait until pending data is written on any
    valid connections that are still active when we reach our limit.
    """

    protocol = _PasteBinHTTPChannel

    def __init__(self, *args, **kw):
        self.active_clients = 0
        self.active_requests = list()
        self._max_requests = kw['max_requests']
        del kw['max_requests']
        self._request_count = 0
        self._stopping_deferred = None
        Site.__init__(self, *args, **kw)

    def getResourceFor(self, request):
        "Override Site so we can track active requests"
        if request.requestHeaders.hasHeader('user-agent'):
            ua = ' '.join(request.requestHeaders.getRawHeaders('user-agent'))
            print('{}: Serving request to User-Agent "{}".'.format(time.asctime(), ua))
        else:
            print('{}: Serving request with no incoming User-Agent header.'.format(time.asctime()))

        # track requsts currently being serviced, so we can nicely
        # shut them off
        self.active_requests.append(request)
        request.notifyFinish().addBoth(self._forget_request, request)

        # see if we've reached the maximum requests
        self._request_count += 1
        if self._max_requests is not None:
            if self._request_count >= self._max_requests:
                d = self.gracefully_stop()
                d.addBoth(lambda x: reactor.stop())

        # call through to parent
        return Site.getResourceFor(self, request)

    def _forget_request(self, request, _):
        self.active_requests.remove(request)

    def _got_client(self):
        self.active_clients += 1

    def _lost_client(self):
        self.active_clients -= 1
        if self.active_clients <= 0 and self._stopping_deferred:
            self._stopping_deferred.callback(None)
            self._stopping_deferred = None

    def gracefully_stop(self):
        "Returns a Deferred that fires when all clients have disconnected."
        if not self.active_clients:
            return defer.succeed(None)
        for request in self.active_requests:
            request.setHeader('connection', 'close')
        self._stopping_deferred = defer.Deferred()
        return self._stopping_deferred


def _progress(percent, tag, message):
    print(util.pretty_progress(percent), message)


async def run(reactor, cfg, tor, dry_run, once, file, count, keys):

    to_share = file.read().encode('utf8')
    file.close()

    # stealth auth. keys
    authenticators = []
    if keys:
        for x in range(keys):
            authenticators.append('carml_%d' % x)

    if len(authenticators):
        print(len(to_share), "bytes to share with",
              len(authenticators), "authenticated clients.")
    else:
        print(len(to_share), "bytes to share.")
    sys.stdout.flush()

    if dry_run:
        print('Not launching a Tor, listening on 8899.')
        ep = serverFromString(reactor, 'tcp:8899:interface=127.0.0.1')
    elif tor is None:
        print("Launching Tor.")
        tor = await txtorcon.launch(reactor, progress_updates=_progress)

    if not authenticators:
        ep = tor.create_onion_endpoint(80, version=3)
    else:
        authdir = mkdtemp()
        print("created: {}".format(authdir))

        def delete():
            print("deleting: {}".format(authdir))
            rmtree(authdir)
        reactor.addSystemEventTrigger('before', 'shutdown', delete)

        ep = tor.create_filesystem_authenticated_onion_endpoint(
            80,
            version=2,
            hs_dir=authdir,
            auth=AuthStealth(authenticators),
        )

    root = Resource()
    data = Data(to_share, 'text/plain')
    root.putChild(b'', data)

    if once:
        count = 1
    port = await ep.listen(PasteBinSite(root, max_requests=count))
    onion = port.onion_service

    if keys == 0:
        clients = None
    else:
        # FIXME
        clients = [
            onion.get_client(n)
            for n in onion.client_names()
        ]

    host = port.getHost()
    if dry_run:
        print("Try it locally via http://127.0.0.1:8899")

    elif clients:
        print("You requested stealth authentication.")
        print("Tor has created %d keys; each key should be given to one person." % len(clients))
        print('They can set one using the "HidServAuth" torrc option, like so:')
        print("")
        for client in clients:
            print("  HidServAuth %s %s" % (client.hostname, client.auth_token))
        print("")
        print("Alternatively, any Twisted endpoint-aware client can be given")
        print("the following string as an endpoint:")
        print("")
        for client in clients:
            print("  tor:%s:authCookie=%s" % (client.hostname, client.auth_token))
        print("")
        print("For example, using carml:")
        print("")
        for client in clients:
            print("  carml copybin --service tor:%s:authCookie=%s" % (client.hostname, client.auth_token))

    else:
        print("People using Tor Browser Bundle can find your paste at (once the descriptor uploads):")
        print("\n   http://{0}\n".format(host.onion_uri))
        print("for example:")
        print("   torsocks curl -o data.asc http://{0}\n".format(host.onion_uri))
        if not count:
            print("Type Control-C to stop serving and shut down the Tor we launched.")
        print("The private key is:")
        print(onion.private_key)

    reactor.addSystemEventTrigger('before', 'shutdown',
                                  lambda: print(util.colors.red('Shutting down.')))
    # we never callback() on this, so we serve forever
    d = defer.Deferred()
    await d
