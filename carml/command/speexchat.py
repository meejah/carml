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
        if True:
            audiodev = 'plughw:CARD=B20,DEV=0'
            src = 'alsasrc device="%s"' % audiodev
            outgoing = src + ' ! audioconvert ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=%d' % self.base_port
            if self.base_port != 5000:
                outgoing = 'audiotestsrc ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=%d' % self.base_port
            outpipe = gst.parse_launch(outgoing)
            print("gstreamer: %s" % outgoing)
            outpipe.set_state(gst.STATE_PLAYING)

    def _microphone_connected(self, inport):
        print("MICROPHONE %s" % inport)
        incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! autoaudiosink' % (self.base_port + 1)
        if self.base_port != 5000:
            incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! filesink location=kerblam.speex' % (self.base_port + 1)
        else:
            incoming = 'tcpserversrc host=localhost port=%d ! queue ! decodebin ! audioconvert ! filesink location=kerding.speex' % (self.base_port + 1)
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
        if self.microphone:
            self.microphone.transport.write(data)

    def connectionLost(self, reason):
        print("Disconnect: " + str(reason))
        for proto in [self.microphone, self.speakers]:
            if proto:
                proto.transport.loseConnection()


class HiddenServiceFactory(Factory):
    protocol = GStreamerToHiddenServiceProtocol


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

    @defer.inlineCallbacks
    def run(self, options, mainoptions, state):
        "ICarmlCommand API"

        if options['client']:
            ep = TCP4ClientEndpoint(reactor, '127.0.0.1', 5050)
            proto = GStreamerToHiddenServiceProtocol(5005)
            p = yield connectProtocol(ep, proto)
            print("Connected. %s" % p)

        else:
            ep = TCP4ServerEndpoint(reactor, 5050, interface="127.0.0.1")
            factory = HiddenServiceFactory()
            p = yield ep.listen(factory)
            print("Listening. %s" % p)
        
        yield defer.Deferred()
        return

        if True:
            audiodev = 'plughw:CARD=B20,DEV=0'
            src = 'alsasrc device="%s"' % audiodev
            outgoing = src + ' ! audioconvert ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=5000'
            incoming = 'tcpserversrc host=localhost port=5001 ! queue ! decodebin ! audioconvert ! autoaudiosink'

            inpipe = gst.parse_launch(incoming)
#            pipeline = gst.parse_launch(outgoing + '  ' + incoming)
            # for the client/callee we do the opposite -- just reverse the ports.
            inpipe.set_state(gst.STATE_PLAYING)

        # so, we READ from the microphone pipe and write that to the hiddenservice (if we have a client)
        # ...and any data we get from the hiddenservice we write to the speaker pipe
        microphone = TCP4ServerEndpoint(reactor, 5000, interface="127.0.0.1")
        speaker = TCP4ClientEndpoint(reactor, "127.0.0.1", 5001)
        hiddenservice = TCP4ServerEndpoint(reactor, 6000)

        # XXX TODO if we're the initiator, we create a hidden service
        # and listen on it; if instead we're the client, we connect to
        # the hidden-service that the other person started

        proto = CrossConnectProtocol(None)
        factory = CrossConnectProtocolFactory(proto)

        inport = yield microphone.listen(factory)
        outgoing = yield connectProtocol(speaker, proto)

        audiodev = 'plughw:CARD=B20,DEV=0'
        src = 'alsasrc device="%s"' % audiodev
        outgoing = src + ' ! audioconvert ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=5000'
        outpipe = gst.parse_launch(outgoing)
        outpipe.set_state(gst.STATE_PLAYING)

# here's some ASCII art of what we've got going on now:
#
# mic -> speex -> localhost:5000 --> CrossConnectProtocol -> localhost:5001 -> un-speex -> speaker
#
# what we WANT:
#
# mic-A -> speex -> localhost:5000 -> CCProtocol <-Tor-> CCProtocol -> localhost:5001 -> un-speex -> speaker-B
# speaker-A <- un-speex <- localhost:5001 <- CCProtocol <-Tor-> CCProtocol <- localhost:5000 <- speex <- mic-B
#
#
#     mic-A ->    speex -> localhost:5000 | <-> CCProtocol <---> CCProtocol <-> | localhost:5001 -> un-speex -> speaker-B
# speaker-A <- un-speex <- localhost:5001 |                 Tor                 | localhost:5000 <-    speex <- mic-B
#
# So that's 2 GStreamer pipelines per side and 1 Tor connection.
#
# TODO:
# 1. CrossConnectProtocol's "other" thing has to be a tor-based connection to the "other" speexchat instance
# 2. change when we launch the gstream pipelines
#    (i.e. inside CrossConnectProtocol?)

        # never exit
        yield defer.Deferred()
        return

        if False:
            config = txtorcon.TorConfig(state.protocol)
            yield config.post_bootstrap

            hs = txtorcon.HiddenService(config, '/tmp/foo', ['5000 127.0.0.1:5000', '5001 127.0.0.1:5001'])
            config.hiddenservices.append(hs)
            yield config.save()

            print("Created hidden-service on 127.0.0.1:5000")
            print(hs.hostname)

        from subprocess import Popen, PIPE
        import gst
        
        # for the hoster/initiator
        audiodev = 'plughw:CARD=B20,DEV=0'
        src = 'alsasrc device="%s"' % audiodev
        #src = 'audiotestsrc'
        if options.client:
            outgoing = src + ' ! audioconvert ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=6000'
            incoming = 'tcpserversrc host=localhost port=6000 ! queue ! decodebin ! audioconvert ! autoaudiosink'
        else:
            outgoing = src + ' ! audioconvert ! speexenc vbr=true ! queue ! tcpclientsink host=localhost port=5000'
            incoming = 'tcpserversrc host=localhost port=5000 ! queue ! decodebin ! audioconvert ! autoaudiosink'

        pipeline = gst.parse_launch(outgoing + '  ' + incoming)

        # for the client/callee we do the opposite -- just reverse the ports.
        
        pipeline.set_state(gst.STATE_PLAYING)

        d = defer.Deferred()
        # READY means "not playing"
        reactor.callLater(10, pipeline.set_state, gst.STATE_READY)
        reactor.callLater(11, d.callback, pipeline)

        yield d
        return


        args = [
            'gst-launch-0.10', 
            'v4l2src', '!',
            'speex/x-raw-yuv,device=/dev/speex0,width=640,height=480,framerate=(fraction)10/1', '!',
            'queue', '!',
##            'image/jpeg,framerate=10/1', '!',
            'xvimagesink,sync=false'
        ]
        print(' '.join(args))
        gstream = Popen(args, stdout=PIPE)
        # FIXME use Twisted's spawnProcess!

        gstream.wait()
        yield defer.succeed(gstream)
        return
        # we never callback() on this, so we serve forever
        d = defer.Deferred()
        yield d

# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = SpeexChatCommand()
