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
from twisted.web.http import HTTPChannel
from twisted.web.static import Data
from twisted.web.resource import Resource
from twisted.web.server import Site

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
#  user A ("caller") --------------------------------------|                user B (callee)
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


class PassThroughProtocol(Protocol):
    def __init__(self, other):
        print("PassThroughProtocol()")
        self.other = other

    def connectionMade(self):
        print("connection made %s %s" % (self, self.other))

    def dataReceived(self, data):
        print("%d bytes" % len(data))
        if self.other:
            self.other.transport.write(data)

    def connectionLost(self, reason):
        print("Lost: " + str(reason))
        if self.other:
            self.other.transport.loseConnection()


class PassThroughProtocolFactory(Factory):
    protocol = PassThroughProtocol
    def __init__(self, other):
        self.other = other

    def buildProtocol(self, addr):
        p = self.protocol(self.other)
        # cross-connect the two Protocol instances
        self.other.other = p
        return p


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

        # so, we READ from the microphone pipe and write that to the hiddenservice (if we have a client)
        # ...and any data we get from the hiddenservice we write to the speaker pipe
        microphone = TCP4ServerEndpoint(reactor, 5000, interface="127.0.0.1")
        speaker = TCP4ClientEndpoint(reactor, "127.0.0.1", 5001)
        hiddenservice = TCP4ServerEndpoint(reactor, 6000)

        proto = PassThroughProtocol(None)
        factory = PassThroughProtocolFactory(proto)

        port = yield microphone.listen(factory)
        print("IN! " + str(port) + " " + str(factory))

        outgoing = yield connectProtocol(speaker, proto)
        print("OUT! " + str(outgoing))

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
