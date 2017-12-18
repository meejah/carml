from __future__ import print_function
import sys
import time
import functools

import zope.interface
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.endpoints import serverFromString
from twisted.web.http import HTTPChannel
from twisted.web.static import Data
from twisted.web.resource import Resource
from twisted.web.server import Site

from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint


@inlineCallbacks
def run(reactor, cfg, tor, ports):

    def info(msg):
        if 'Service descriptor (v2) stored' in msg:
            got_upload.callback(None)
    got_upload = Deferred()
    tor.protocol.add_event_listener('INFO', info)

    hs = txtorcon.EphemeralHiddenService(ports)
    yield hs.add_to_tor(tor.protocol)
    print("Created HS", hs.hostname)

    def remove():
        print("removing hidden-service")
        return hs.remove_from_tor(tor.protocol)
    reactor.addSystemEventTrigger('before', 'shutdown', remove)

    print("...waiting for descriptor upload")
    yield got_upload
    print("Got one.", time.asctime())

    # we never callback() on this, so we serve forever
    d = Deferred()
    yield d


def _remove_service(config, hs):
    config.hiddenservices.remove(hs)
    return config.save()
