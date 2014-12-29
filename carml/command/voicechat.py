from __future__ import print_function
import sys
import time
import functools

import zope.interface
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.internet import reactor # FIXME, use passed-in one
from twisted.internet.endpoints import serverFromString
from twisted.internet.endpoints import clientFromString
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

#
# DOCUMENTATION notes
#
# things needed on debian:
#  apt-get install liblzma-dev 

# FIXME NOTES
#
# . athena points out i should be using fixed-rate codec. makes sense.
#    -> speex supports fixed bit-rates
#    -> xiph.org says speex obsolete, use opus
#    -> ...but opus in gstreamer's "bad" plugins
#    -> something like "5kbps" is super-low, that's 625 bytes/second...
#    -> so 2 tor cells per second would be ... 1024Bytes/s = 8192bps = 8kps
#

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
#
#
#      mic -> gstreamer-input  -> Proxy <-> Tor HS <-> Proxy -> gstreamer-output -> speakers
# speakers <- gstreamer-output <-                            <- gstreamer-input  <- mic
#
#  `------------{ initiator }---------'  Internet/Tor  `--------------{ responder }--------'
#
# "gstreamer-input" is a gstreamer pipeline:
#    autoaudiosrc ! audioconvert ! <encoderstuff> ! queue ! tcpclientsink 127.0.0.1:<port0>
# "gstreamer-output" is a gstreamer pipeline:
#    tcpserversrc 127.0.0.1:<port1> ! queue ! <decoderstuff> ! audioconvert ! autoaudiosink
#
# The "Proxy" things are Twisted Protocols that cross-connect two
# streams. In this case, they make the "input" stream go to the
# write-side of the hidden-service, and take the read-side of the
# hidden-service and forward it to the "output" gstreamer.
#
# <encoderstuff> and <decoderstuff> are bits of gstreamer to make the
# encoding "go". We're using OGG as a container, and opus, speex or
# vorbis codecs. On suggestion of athena, I'm trying to use fixed-rate
# encodings.
#
#
# Use twisted.protocols.portforward instead of CrossConnect thing
#
# For initiator:
#
#      mic -> gstreamer -> localhost:micport (connects)
# speakers <- gstreamer <- localhost:spkrport (listens)
#
# localhost:micport -> portforward.ProxyServer -> tor (HS listen port)
#               tor -> portforward.ProxyClient -> localhost:spkrport
#
# So when Tor listening-port gets a connection, it wants to forward
# that on so as to connect it up to the speakers, but it *also* wants
# to pump any data from mic out over the tcp stream


gstream_encoder = " speexenc bitrate=16384 ! oggmux "
gstream_decoder = " oggdemux ! speexdec "
gstream_encoder = " vorbisenc bitrate=16384 ! oggmux "
gstream_decoder = " oggdemux ! vorbisdec "
gstream_encoder = " opusenc ! oggmux "
gstream_decoder = " oggdemux ! opusdec "


class VoiceChatOptions(usage.Options):
    """
    """

    optFlags = [
    ]

    optParameters = [
        ('client', 'c', None, 'Connect to existing session (i.e. someone sent you a dot-onion).', str),
    ]


# FIXME can't we use something from Twisted? Or "Tubes", which should
# be released shortly for realz?
# FIXME at least, we should be doing producer/consumer stuff so we don't bufferbloat
class CrossConnectProtocol(Protocol):
    def __init__(self, other):
        #print("CrossConnectProtocol()")
        self.other = other

#    def connectionMade(self):
#        print("connection made %s %s" % (self, self.other))

    def dataReceived(self, data):
        if self.other and self.other.transport:
            ##print("%d bytes" % len(data))
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

class VoiceChatMixIn(object):
    """
    This mixes in helper methods for both InitiatorProtocol and
    ResponderProtocol. It expects the following attributes to exist on
    self:

       port0, port1: arbitrary, free TCP ports
       reactor: the reactor in use
    """

    @defer.inlineCallbacks
    def _create_microphone(self):
        """Create the gstreamer input-side chain, which means:

        mic -> gstreamer -> localhost:port0 -> CrossConnectProtocol:port0 -> ...

        The deferred callsback once CrossConnectProtocol is connected
        to gstreamer.

        """

        # here, we create a listener on port0 to which the gstreamer
        # microphone pipeline will connect.
        ## FIXME if, e.g., we spell reactor "blkmalkmf" then we lose the error; something missing .addErrback!
        microphone = TCP4ServerEndpoint(reactor, self.port0, interface="127.0.0.1")
        port = yield microphone.listen(CrossConnectProtocolFactory(self))
        print("microphone listening", port)

        #outgoing = 'autoaudiosrc ! audioconvert ! %s ! queue ! tcpclientsink host=localhost port=%d' % (gstream_encoder, self.port0)
        outgoing = 'audiotestsrc ! audioconvert ! %s ! queue ! tcpclientsink host=localhost port=%d' % (gstream_encoder, self.port0)
        outpipe = gst.parse_launch(outgoing)
        print("gstreamer: %s" % outgoing)
        outpipe.set_state(gst.STATE_PLAYING)
        defer.returnValue(port)

    @defer.inlineCallbacks
    def _create_speakers(self):
        """
        """

        incoming = 'tcpserversrc host=localhost port=%d ! queue ! %s ! audioconvert ! autoaudiosink' % (self.port1, gstream_decoder)
        print("gstreamer: %s" % incoming)
        inpipe = gst.parse_launch(incoming)
        inpipe.set_state(gst.STATE_PLAYING)

        speaker = TCP4ClientEndpoint(reactor, "127.0.0.1", self.port1)
        proto = CrossConnectProtocol(self)
        print("speakers connected", proto)
        yield connectProtocol(speaker, proto)
        defer.returnValue(proto)


class InitiatorProtocol(Protocol, VoiceChatMixIn):
    """
    This is for the person who runs the hidden-service. That is,
    whomever initiates the call. Once they have the hidden-service
    address, they communicate it to the other party (securely) who
    then use this same command with --client

    FIXME XXX isn't this now precisely the same as ResponderProtocol

    """
    def __init__(self, reactor, port0=5000, port1=5001):
        """
        :param port0: arbitrary, unused TCP port
        :param port1: arbitrary, unused TCP port
        """
        self.microphone = None
        self.speakers = None
        self.reactor = reactor
        self.port0 = port0
        self.port1 = port1
        log.msg("initiate, on ports %d and %d" % (port0, port1))
        print("init", port0, port1)

    @defer.inlineCallbacks
    def connectionMade(self):
        '''
        The other end has connected -- that is, we've got the remote side
        of the call on the line via Tor. So we start our GStreamer pipelines.
        '''
        print("Client connected:", self.transport.getPeer())
        self.microphone = yield self._create_microphone()
        self.speakers = yield self._create_speakers()

        self.transport.registerProducer(self.speakers.transport, True)
        self.speakers.transport.registerProducer(self, True)
        self.speakers.transport.resumeProducing()

        print("Done:\n   %s\n   %s\n" % (self.microphone, self.speakers))

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
    def __init__(self, reactor, port0, port1):
        self.reactor = reactor
        self.port0 = port0
        self.port1 = port1

    def buildProtocol(self, addr):
        return InitiatorProtocol(self.reactor, self.port0, self.port1)


class VoiceChatCommand(object):

    """
    We start a hidden-serivce that is a bi-directional pipe for
    SPEEX-encoded audio data (via gstreamer).
    """
    zope.interface.implements(ICarmlCommand, IPlugin)

    name = 'voicechat'
    help_text = """Start a bi-directional voice chat on a hidden-service."""
#    build_state = True
#    controller_connection = True
    build_state = False
    controller_connection = False
    options_class = VoiceChatOptions

    def validate(self, options, mainoptions):
        "ICarmlCommand API"

    def run(self, options, mainoptions, state):
        "ICarmlCommand API"

        if options['client']:
            return self.run_client(reactor, options, mainoptions, state)
        return self.run_server(reactor, options, mainoptions, state)

    @defer.inlineCallbacks
    def run_client(self, reactor, options, mainoptions, state):
        port0 = yield txtorcon.util.available_tcp_port(reactor)
        port1 = yield txtorcon.util.available_tcp_port(reactor)
        print("ports: %d %d" % (port0, port1))

        ##'127.0.0.1'
        ##ep = TCP4ClientEndpoint(reactor, options['client'], 5050)
        ep = clientFromString(reactor, options['client'])
        proto = InitiatorProtocol(reactor, port0, port1)
        p = yield connectProtocol(ep, proto)
        print("Connected. %s" % p)
        yield defer.Deferred()

    @defer.inlineCallbacks
    def run_server(self, reactor, options, mainoptions, state):
        port0 = yield txtorcon.util.available_tcp_port(reactor)
        port1 = yield txtorcon.util.available_tcp_port(reactor)
        print("ports: %d %d" % (port0, port1))

        ep = TCP4ServerEndpoint(reactor, 5050)#, interface="127.0.0.1")
        # fixme should allow to specify private key, too
        #ep = serverFromString(reactor, "onion:5050")  ##TCP4ServerEndpoint(reactor, 5050)#, interface="127.0.0.1")
        factory = InitiatorFactory(reactor, port0, port1)
        p = yield ep.listen(factory)
        print("Listening. %s (%s)" % (p, p.getHost()))
        yield defer.Deferred()

# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = VoiceChatCommand()
