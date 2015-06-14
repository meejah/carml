from __future__ import print_function
import sys
import time
import functools

from zope.interface import implementer
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.web.iweb import IAgentEndpointFactory
from twisted.web.client import Agent
from twisted.internet import reactor
from twisted.internet.protocol import Protocol


from carml.interface import ICarmlCommand
from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint


class CopyBinOptions(usage.Options):
    """
    """

    optFlags = [
    ]

    optParameters = [
        ('service', 's', None, 'The endpoint you were given to download from.'),
    ]

@implementer(IAgentEndpointFactory)
class EndpointFactory(object):
    def __init__(self, ep):
        self.endpoint = ep

    def endpointForURI(self, uri):
        '''IAgentEndpointFactory API'''
        return self.endpoint


def receive(req):
    d = defer.Deferred()
    req.deliverBody(BodyReceiver(d))
    return d


class BodyReceiver(Protocol):
    def __init__(self, d):
        self.data = ''
        self.done = d

    def dataReceived(self, data):
        self.data += data

    def connectionLost(self, reason):
        self.done.callback(self.data)


@implementer(ICarmlCommand, IPlugin)
class CopyBinCommand(object):
    """
    The opposite of "carml pastebin" -- download something from a
    pastebin, possibly using stealth tor authentication as well.
    """

    name = 'copybin'
    help_text = """Download something from a "pastebin" hidden-service."""
    build_state = False
    controller_connection = True
    options_class = CopyBinOptions

    def validate(self, options, mainoptions):
        "ICarmlCommand API"
        if not options['service']:
            raise RuntimeError("--service option required")

    @defer.inlineCallbacks
    def run(self, options, mainoptions, proto):
        "ICarmlCommand API"

        config = txtorcon.TorConfig(proto)
        yield config.post_bootstrap

        socks = yield proto.get_info('net/listeners/socks')
        socks = socks['net/listeners/socks']
        socks_host, socks_port = socks.split(':')

        args = options['service'].split(':')
        onion = args[1]
        cookie = args[2].split('=')[1]
        ep = txtorcon.TorClientEndpoint(
            onion, 80,
            socks_hostname=socks_host, socks_port=int(socks_port)
        )

        auth = '%s %s' % (onion, cookie)
        if auth not in config.HidServAuth:
            config.HidServAuth.append(auth)
        yield config.save()

        agent = Agent.usingEndpointFactory(reactor, EndpointFactory(ep))
        res = yield agent.request('GET', 'http://%s/' % onion)
        print("Response:", res.code)
        print("bytes:", res.length)
        data = yield receive(res)
        print(data)


# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = CopyBinCommand()
