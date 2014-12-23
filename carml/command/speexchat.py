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
        if self.other and self.other.transport:
            self.other.transport.write(data)

    def connectionLost(self, reason):
        print("crossconnect %s lost: " % (str(self), str(reason)))
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


class InitiatorProtocol(Protocol):
    def __init__(self, port0=5000, port1=5001):
        self.microphone = None
        self.speakers = None
        self.port0 = port0
        self.port1 = port1
        print('INITiate! %d %d' % (port0, port1))

    def error(self, foo):
        print("ERROR: %s" % foo)

    def create_microphone(self):
        # here, we create a listener on port0 to which the gstreamer
        # microphone pipeline will connect.
        ## FIXME if, e.g., we spell reactor "blkmalkmf" then we lose the error; something missing .addErrback!
        microphone = TCP4ServerEndpoint(reactor, self.port0, interface="127.0.0.1")
        d = microphone.listen(CrossConnectProtocolFactory(self))
        d.addCallback(self._microphone_connected).addErrback(self.error)

        # the gstreamer mic -> port0 pipeline
        audiodev = 'plughw:CARD=B20,DEV=0'
        src = 'alsasrc device="%s"' % audiodev
        outgoing = src + ' ! audioconvert ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=%d' % self.port0
        outpipe = gst.parse_launch(outgoing)
        print("gstreamer: %s" % outgoing)
        outpipe.set_state(gst.STATE_PLAYING)

    def _microphone_connected(self, inport):
        # now we create the gstreamer -> speakers pipeline, listening
        # on port1
        incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! autoaudiosink' % (self.port1)
        incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! filesink location=xxx.speex' % (self.port1)
        inpipe = gst.parse_launch(incoming)
        inpipe.set_state(gst.STATE_PLAYING)

        # ...and then connect the hidden service up to gstreamer
        speaker = TCP4ClientEndpoint(reactor, "127.0.0.1", self.port1)
        proto = CrossConnectProtocol(self)
        d = connectProtocol(speaker, proto)
        self.speakers = proto
        d.addCallback(self._speaker_connected)

    def _speaker_connected(self, proto):
        print("Liftoff! %s" % proto)

    def connectionMade(self):
        '''
        The other end has connected -- that is, we've got the remote side
        of the call on the line. So we start our GStreamer pipelines.
        '''
        print("Client connected:", self.transport.getPeer())
        self.create_microphone()

    def dataReceived(self, data):
        '''
        The remote side is sending us data. It is SPEEX audio data, so dump it
        into the speakers (if we've got those pipelines up and running).
        '''
        if self.speakers and self.speakers.transport:
            #print('DING %d' % len(data))
            self.speakers.transport.write(data)

    def connectionLost(self, reason):
        print("Disconnect: " + str(reason))
        for proto in [self.microphone, self.speakers]:
            if proto:
                proto.transport.loseConnection()


class InitiatorFactory(Factory):
    protocol = InitiatorProtocol


class ResponderProtocol(Protocol):
    def __init__(self, port0, port1):
        self.port0 = port0
        self.port1 = port1

    def connectionMade(self):
        print("connection made %s" % (self))
        mic = TCP4ServerEndpoint(reactor, self.port1, interface="127.0.0.1")
        self.factory = CrossConnectProtocolFactory(self)
        d = mic.listen(self.factory)
        d.addCallback(self._microphone_connected).addErrback(self.error)

    def error(self, e):
        print("ERR: %s" % e)
        return None

    def _microphone_connected(self, _):
        print(str(_))
        print("microphone! port %d" % self.port0)
        outgoing = 'audiotestsrc ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=%d' % self.port1
        outpipe = gst.parse_launch(outgoing)
        outpipe.set_state(gst.STATE_PLAYING)


        incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! autoaudiosink' % self.port0
#        incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! filesink location=zzz.speex' % self.port0
        inpipe = gst.parse_launch(incoming)
        inpipe.set_state(gst.STATE_PLAYING)

        speaker = TCP4ClientEndpoint(self.reactor, "127.0.0.1", self.port0)
        self.proto = CrossConnectProtocol(self)
        d = connectProtocol(speaker, self.proto)
        d.addCallback(print)


    def dataReceived(self, data):
        print("responder data", len(data))
        if self.proto and self.proto.transport:
            self.proto.transport.write(data)

    def connectionLost(self, reason):
        print("responder lost: " + str(reason))
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
        port0 = yield txtorcon.util.available_tcp_port(reactor)
        port1 = yield txtorcon.util.available_tcp_port(reactor)
        print("ports: %d %d" % (port0, port1))

        ep = TCP4ClientEndpoint(reactor, '127.0.0.1', 5050)
        proto = ResponderProtocol(port0, port1)
        p = yield connectProtocol(ep, proto)
        print("Connected. %s" % p)
        yield defer.Deferred()

    @defer.inlineCallbacks
    def run_server(self, options, mainoptions, state):
        ep = TCP4ServerEndpoint(reactor, 5050, interface="127.0.0.1")
        factory = InitiatorFactory()
        p = yield ep.listen(factory)
        print("Listening. %s" % p)
        yield defer.Deferred()

# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = SpeexChatCommand()
