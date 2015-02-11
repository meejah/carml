from __future__ import print_function
import sys
import time
import functools

import zope.interface
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.internet import reactor  # FIXME, use passed-in one
from twisted.internet import error
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

# FIXME + NOTES
#
# . athena points out i should be using fixed-rate codec. makes sense.
#    -> speex supports fixed bit-rates
#    -> xiph.org says speex obsolete, use opus
#    -> ...but opus in gstreamer's "bad" plugins

# OVERVIEW
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
# vorbis codecs. I'm trying to use fixed-rate encodings.


# If you're playing with different audio codecs, make sure the server
# and client agree on what the de-coder is. You'll also want to look
# in "run_server" below and use the test-setup to test over public
# internet/LAN so you're not bringing up lots of hiddenservices "for
# real"

# Okay, I recevied from good feedback from Vincent Penquerc'h
# https://lists.torproject.org/pipermail/tor-dev/attachments/20150210/56645b47/attachment.mht
#
# Some TODOs from that:
#
# + Opus: yes
# - double-check we're getting constant bit-rate:
#   GST_DEBUG_FILE=/tmp/blarg
#   GST_DEBUG=GST_SCHEDULING:3
#   -> check that byte-sizes of the buffers doesn't change
# - Use RTP instead of OGG for muxing


# have never seen this work with any "bitrate" options. works without
# any such options.
gstream_encoder = " vorbisenc max-bitrate=16384 ! oggmux "
gstream_decoder = " oggdemux ! vorbisdec "

# this works, but SPEEX is deprecated in favour of opus according to
# xiph.org In any case, OPUS sounds better (but might be using VBR?)
gstream_encoder = " speexenc bitrate=16384 ! oggmux "
gstream_decoder = " oggdemux ! speexdec "

# this works, but not sure how to get fixed-bitrate for sure
gstream_encoder = " opusenc bitrate=16000 constrained-vbr=false ! oggmux "
gstream_decoder = " oggdemux ! opusdec "

# trying to make RTP work instead of OGG
# see also http://gstreamer-devel.966125.n4.nabble.com/Need-help-with-using-OPUS-over-RTP-td4661409.html
gstream_encoder = " audioresample ! opusenc bitrate=16000 constrained-vbr=false ! rtpopuspay "
gstream_decoder = " gstrtpjitterbuffer latency=100 do-lost=true ! rtpopusdepay ! opusdec plc=true "

gstream_encoder = " audioresample ! opusenc bitrate=32000 constrained-vbr=false ! rtpopuspay "
gstream_decoder = " rtpopusdepay ! opusdec "



class VoiceChatOptions(usage.Options):
    """
    """

    optFlags = [
        ('sanity', 's', 'Sanity-check your setup; should play audiotestsrc for 1 second and exit.')
    ]

    optParameters = [
        ('client', 'c', None, 'Connect to existing session (i.e. someone sent you a dot-onion).', str),
        ('src', '', 'autoaudiosrc', 'String to give gstreamer as audio source.', str),
        ('sink', '', 'autoaudiosink', 'String to give gstreamer as audio sink', str),
    ]


# FIXME can't we use something from Twisted? Or "Tubes", which should
# be released shortly for realz?
# FIXME at least, we should double-check the producer/consumer stuff so we don't bufferbloat
class CrossConnectProtocol(Protocol):
    def __init__(self, other):
        # print("CrossConnectProtocol()")
        self.other = other

#    def connectionMade(self):
#        print("connection made %s %s" % (self, self.other))

    def dataReceived(self, data):
        if self.other and self.other.transport:
            # print("%d bytes" % len(data))
            self.other.transport.write(data)

    def connectionLost(self, reason):
        print("crossconnect %s lost: " % (str(self), str(reason)))
        if self.other:
            self.other.transport.loseConnection()


class CrossConnectProtocolFactory(Factory):
    def __init__(self, other):
        self.other = other

    def buildProtocol(self, addr):
        p = CrossConnectProtocol(self.other)
        # cross-connect the two Protocol instances
        self.other.other = p
        return p


class AudioProtocol(Protocol):
    """
    This protocol is re-used for both the listening-side, and the
    client-side. On the listening side, it's created via AudioFactory
    (and is listening on hidden-service port). On the client side it
    just connects.

       port0, port1: arbitrary, free TCP ports
       reactor: the reactor in use
       all_done: a Deferred we call/err back on when done
    """
    def __init__(self, reactor, all_done, port0, port1, src, sink):
        """
        :param port0: arbitrary, unused TCP port
        :param port1: arbitrary, unused TCP port
        """
        assert '!' not in sink
        assert '!' not in src
        self.src = src
        self.sink = sink
        self.microphone = None
        self.speakers = None
        self.reactor = reactor
        self.port0 = port0
        self.port1 = port1
        self.all_done = all_done
        log.msg("initiate, on ports %d and %d" % (port0, port1))
        # print("init", port0, port1)

    def connectionMade(self):
        '''
        The other end has connected -- that is, we've got the remote side
        of the call on the line via Tor. So we start our GStreamer pipelines.
        '''

        d = self._connect_audio()
        def foo(e):
            self.all_done.errback(e)
            return e
        d.addErrback(foo)

    @defer.inlineCallbacks
    def _connect_audio(self):
        print("Client connected:", self.transport.getPeer())
        self.microphone = yield self._create_microphone()
        self.speakers = yield self._create_speakers()

        self.transport.registerProducer(self.speakers.transport, True)
        self.speakers.transport.registerProducer(self, True)
        self.speakers.transport.resumeProducing()

        # print("Done:\n   %s\n   %s\n" % (self.microphone, self.speakers))

    def dataReceived(self, data):
        '''
        The remote side is sending us data. It is audio data, so dump it
        into the speakers (if we've got those pipelines up and running).
        '''
        if self.speakers and self.speakers.transport:
            self.speakers.transport.write(data)

    def connectionLost(self, reason):
        print("Disconnect: " + reason.getErrorMessage())
        self.outpipe.set_state(gst.STATE_PAUSED)
        self.outpipe = None
        if self.microphone:
            self.microphone.loseConnection()
            self.microphone = None
        if self.speakers and self.speakers.transport:
            self.speakers.transport.loseConnection()
            self.speakers = None
        self.all_done.callback(None)

    @defer.inlineCallbacks
    def _create_microphone(self):
        """Create the gstreamer input-side chain, which means:

        mic -> gstreamer -> localhost:port0 -> ...

        The deferred callsback once CrossConnectProtocol is connected
        to gstreamer.
        """

        # here, we create a listener on port0 to which the gstreamer
        # microphone pipeline will connect.
        # FIXME if, e.g., we spell reactor "blkmalkmf" then we lose the error; something missing .addErrback!
        microphone = TCP4ServerEndpoint(reactor, self.port0, interface="127.0.0.1")
        port = yield microphone.listen(CrossConnectProtocolFactory(self))
        # print("microphone listening", port)

        # XXX if you need a custom gstreamer src, change autoaudiosrc
        # here -- should maybe provide command-line option?
        outgoing = '%s ! audioconvert ! %s ! queue ! tcpclientsink host=localhost port=%d' % (self.src, gstream_encoder, self.port0)
        self.outpipe = gst.parse_launch(outgoing)
        print("gstreamer: %s" % outgoing)
        self.outpipe.set_state(gst.STATE_PLAYING)
        defer.returnValue(port)

    @defer.inlineCallbacks
    def _create_speakers(self):
        """
        Similar to above, but gstreamer pipeline for the speaker pipeline

        ... -> localhost:port1 -> gstreamer -> speakers
        """

        incoming = 'tcpserversrc host=localhost port=%d ! queue ! %s ! audioconvert ! %s' % (self.port1, gstream_decoder, self.sink)
        print("gstreamer: %s" % incoming)
        inpipe = gst.parse_launch(incoming)
        inpipe.set_state(gst.STATE_PLAYING)

        speaker = TCP4ClientEndpoint(reactor, "127.0.0.1", self.port1)
        proto = CrossConnectProtocol(self)
        # print("speakers connected", proto)
        yield connectProtocol(speaker, proto)
        defer.returnValue(proto)


class AudioFactory(Factory):
    """
    Creates AudioProtocol on the server-side with specified ports.
    all_done is a Deferred we will call/err-back on
    """
    def __init__(self, reactor, all_done, port0, port1, src, sink):
        # FIXME what about just and "args" tuple instead?
        self.reactor = reactor
        self.port0 = port0
        self.port1 = port1
        self.all_done = all_done
        self.src = src
        self.sink = sink

    def buildProtocol(self, addr):
        return AudioProtocol(self.reactor, self.all_done, self.port0, self.port1, self.src, self.sink)


class VoiceChatCommand(object):
    """
    We start a hidden-serivce that is a bi-directional pipe for audio
    data (via gstreamer).

    """
    zope.interface.implements(ICarmlCommand, IPlugin)

    name = 'voicechat'
    help_text = """Start a bi-directional voice chat on a hidden-service."""
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
        all_done = defer.Deferred()
        port0 = yield txtorcon.util.available_tcp_port(reactor)
        port1 = yield txtorcon.util.available_tcp_port(reactor)
        # print("ports: %d %d" % (port0, port1))

        # ep = TCP4ClientEndpoint(reactor, '127.0.0.1', 5050)
        ep = clientFromString(reactor, options['client'])
        proto = AudioProtocol(reactor, all_done, port0, port1, options['src'], options['sink'])
        p = yield connectProtocol(ep, proto)
        print("Connected; call should be active.")
        yield all_done
        print("Call has completed.")

    @defer.inlineCallbacks
    def run_server(self, reactor, options, mainoptions, state):
        all_done = defer.Deferred()
        port0 = yield txtorcon.util.available_tcp_port(reactor)
        port1 = yield txtorcon.util.available_tcp_port(reactor)
        # print("ports: %d %d" % (port0, port1))

        # FIXME take an endpoint string from client? or part of one?
        # FIXME should allow to specify private key, too
        # XXX switch to TCP4ServerEndpoint(reactor, 5050) for testing
        # on public interface

        print("GST:", gst.version())
        if options['sanity']:
            print("sanity-test an opus pipeline with your gstreamer")
            print("if you rip your headphones off due to loud sound, it works")
            pipeline = 'audiotestsrc ! ' + gstream_encoder + ' ! queue ! ' + \
                       gstream_decoder + ' ! autoaudiosink '
            pipe = gst.parse_launch(pipeline)
            print("starting")
            pipe.set_state(gst.STATE_PLAYING)
            import time
            time.sleep(1)
            print("stoping")
            pipe.set_state(gst.STATE_PAUSED)
            import sys
            sys.exit(0)

        if False:
            # connect to system tor, add a hidden-service (FRAGILE!)
            ep = txtorcon.TCPHiddenServiceEndpoint.system_tor(
                reactor, clientFromString(reactor, "tcp:localhost:9051"), 5050,
                "/tmp/voicechat_hidsrv")

        elif False:
            # listen on 0.0.0.0:5050 (PUBLIC!). For testing your setup.
            ep = TCP4ServerEndpoint(reactor, 5050)

        else:
            # launch our own tor, add a hidden-service
            ep = txtorcon.TCPHiddenServiceEndpoint.global_tor(
                reactor, 5050, "/tmp/voicechat_hidsrv")
            def prog(p, tag, msg):
                print(util.pretty_progress(p), msg)
            txtorcon.IProgressProvider(ep).add_progress_listener(prog)

        factory = AudioFactory(reactor, all_done, port0, port1, options['src'], options['sink'])
        p = yield ep.listen(factory)

        try:
            hs = txtorcon.IHiddenService(p)
            toraddr = hs.getHost()
            print("We are listening:", toraddr)
            print("SECURELY tell your friend to run:")
            print('carml voicechat --client tor:%s:%d' % (toraddr.onion_uri, toraddr.onion_port))
        except TypeError as e:
            print("Testing setup; listening PUBLICALLY.")
            print("You are NOT ANONYMOUS. Connect via:", p.getHost())

        yield all_done
        print("Call has completed.")

# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = VoiceChatCommand()
