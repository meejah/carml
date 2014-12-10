from __future__ import print_function
import sys
import time
import functools

import zope.interface
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet.endpoints import serverFromString
from twisted.internet.endpoints import connectProtocol
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Protocol
from twisted.internet.protocol import Factory
from twisted.protocols import portforward
from twisted.web.http import HTTPChannel
from twisted.web.static import Data
from twisted.web.resource import Resource
from twisted.web.server import Site
import gst

from carml.interface import ICarmlCommand
from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint

# okay, on the audio side we have two TCP streams:
#
# initiator-mic -> speex -> initiator:5000 (i.e. outgoing from initiator to client via 5000)
# client-mic -> speex -> initiator:5001 (i.e. outgoint from client to initiator via 5001)
#
#
# actually, new full picture:
#
#  user A ("caller") --------------------------------------.                user B (callee)
#                                                          |
#     mic -> SPEEX -> 127.0.0.1:5000 <-  Python <-> Tor HS | <-> Python -> 127.0.0.1:5001 -> SPEEX -> speaker
# speaker <- SPEEX <- 127.0.0.1:5001 ->                    |            <- 127.0.0.1:5000 <- SPEEX <- mic


class SpeexChatOptions(usage.Options):
    """
    """

    optFlags = [
        ('client', 'c', 'Connect to existing session (i.e. someone sent you a dot-onion).'),
    ]

    optParameters = [
    ]


class CrossConnectProtocol(Protocol):
    def __init__(self, other):
        print("CrossConnectProtocol()")
        self.other = other

    def connectionMade(self):
        print("connection made %s %s" % (self, self.other))

    def dataReceived(self, data):
        #print("%d bytes" % len(data))
        if self.other:
            self.other.transport.write(data)

    def connectionLost(self, reason):
        print("Lost: " + str(reason))
        if self.other:
            self.other.transport.loseConnection()


class CrossConnectProtocolFactory(Factory):
    protocol = CrossConnectProtocol
    def __init__(self, other):
        self.other = other

    def buildProtocol(self, addr):
        p = self.protocol(self.other)
        # cross-connect the two Protocol instances
        self.other.other = p
        return p


class GStreamerToHiddenServiceProtocol(Protocol):
    '''
    This runs as the server-side of the phone connection, listening on
    a local TCP port (127.0.0.1:6000) that's connected to a Hidden
    Service for the TCP stream. It starts up two local GStreamer
    pipelines: one FROM the microphone (127.0.0.1:5000) and one TO the
    speakers (127.0.0.1:5001).

    It only starts the GStreamer pipelines once the other side
    connects to our service. At that point, any data arriving on 6000
    (from the other side, via Tor) goes to the speakers (via
    localhost:5001) -- any data arriving via localhost:5000 goes out
    over the network to the other side.
    '''

    def __init__(self, base_port=5000):
        self.microphone = None
        self.speakers = None
        self.base_port = base_port

    def error(self, foo):
        print("ERROR: %s" % foo)

    def create_microphone(self):
        microphone = TCP4ServerEndpoint(reactor, self.base_port, interface="127.0.0.1")
        factory = CrossConnectProtocolFactory(self)
        print("mic, fac %s %s" % (microphone, factory))
        d = microphone.listen(factory)
        d.addCallback(self._microphone_connected).addErrback(self.error)
        print("DING %s" % d)

        audiodev = 'plughw:CARD=B20,DEV=0'
        src = 'alsasrc device="%s"' % audiodev
        outgoing = src + ' ! audioconvert ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=%d' % self.base_port
        outpipe = gst.parse_launch(outgoing)
        print("gstreamer: %s" % outgoing)
        outpipe.set_state(gst.STATE_PLAYING)

    def _microphone_connected(self, inport):
        return
        print("MICROPHONE %s" % inport)
        incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! autoaudiosink' % (self.base_port + 1)
        inpipe = gst.parse_launch(incoming)
        inpipe.set_state(gst.STATE_PLAYING)

        speaker = TCP4ClientEndpoint(reactor, "127.0.0.1", self.base_port + 1)
        proto = CrossConnectProtocol(self)
        d = connectProtocol(speaker, proto)
        d.addCallback(self._speaker_connected)

    def _speaker_connected(self, outport):
        print("SPEAKER %s" % outport)

    def connectionMade(self):
        '''
        The other end has connected -- that is, we've got the remote side
        of the call on the line. So we start our GStreamer pipelines.
        '''
        print("Connection!")
        self.create_microphone()

    def dataReceived(self, data):
        '''
        The remote side is sending us data. It is SPEEX audio data, so dump it
        into the speakers.
        '''
        print('DING %d' % len(data))
        if self.speakers:
            self.speakers.transport.write(data)

    def connectionLost(self, reason):
        print("Disconnect: " + str(reason))
        for proto in [self.microphone, self.speakers]:
            if proto:
                proto.transport.loseConnection()


class HiddenServiceFactory(Factory):
    protocol = GStreamerToHiddenServiceProtocol


class HiddenServiceClientProtocol(Protocol):
    def connectionMade(self):
        print("connection made %s" % (self))
        incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! autoaudiosink' % 5001
        inpipe = gst.parse_launch(incoming)
        inpipe.set_state(gst.STATE_PLAYING)

        speaker = TCP4ClientEndpoint(reactor, "127.0.0.1", 5001)
        self.proto = CrossConnectProtocol(self)
        d = connectProtocol(speaker, self.proto)

    def dataReceived(self, data):
        if self.proto and self.proto.transport:
            self.proto.transport.write(data)

    def connectionLost(self, reason):
        print("Lost: " + str(reason))
        self.proto.transport.loseConnection()


class SpeexChatCommand(object):

    """
    We start a hidden-serivce that is a bi-directional pipe for
    SPEEX-encoded audio data (via gstreamer).
    """
    zope.interface.implements(ICarmlCommand, IPlugin)

    name = 'speexchat'
    help_text = """Start a bi-directional speex chat on a hidden-service."""
#    build_state = True
#    controller_connection = True
    build_state = False
    controller_connection = False
    options_class = SpeexChatOptions

    def validate(self, options, mainoptions):
        "ICarmlCommand API"

    def run(self, options, mainoptions, state):
        "ICarmlCommand API"

        if options['client']:
            return self.run_client(options, mainoptions, state)
        return self.run_server(options, mainoptions, state)

    @defer.inlineCallbacks
    def run_client(self, options, mainoptions, state):
        ep = TCP4ClientEndpoint(reactor, '127.0.0.1', 5050)
        proto = HiddenServiceClientProtocol()
        p = yield connectProtocol(ep, proto)
        print("Connected. %s" % p)
        yield defer.Deferred()

    @defer.inlineCallbacks
    def run_server(self, options, mainoptions, state):
        ep = TCP4ServerEndpoint(reactor, 5050, interface="127.0.0.1")
        factory = HiddenServiceFactory()
        p = yield ep.listen(factory)
        print("Listening. %s" % p)
        yield defer.Deferred()

# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = SpeexChatCommand()
