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

from carml.interface import ICarmlCommand
from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint


class TempHSOptions(usage.Options):
    """
    """

    optFlags = [
    ]

    optParameters = [
    ]

    def __init__(self):
        usage.Options.__init__(self)
        self['ports'] = []

    def opt_port(self, port):
        "add a port redirect: with a colon, specify a different local port (e.g. \"80\" to pass through or \"80:9876\" to listen locally on 9876). Can be used multiple times."
        self['ports'].append(port)


class TempHSCommand(object):
    """
    Keep an ephemeral hidden-service active as long as this command is
    running.
    """
    zope.interface.implements(ICarmlCommand, IPlugin)

    name = 'temphs'
    help_text = 'Add a temporary hidden-service to the Tor we connect to.'
    build_state = False
    controller_connection = True
    options_class = TempHSOptions

    def validate(self, options, mainoptions):
        "ICarmlCommand API"
        if len(options['ports']) == 0:
            raise RuntimeError("Must specify at least one --port")

    def error(self, e):
        print("ERR: %s" % e)

    @inlineCallbacks
    def run(self, options, mainoptions, proto):
        "ICarmlCommand API"

        def info(msg):
            if 'Service descriptor (v2) stored' in msg:
                got_upload.callback(None)
        got_upload = Deferred()
        proto.add_event_listener('INFO', info)

        hs = txtorcon.EphemeralHiddenService(options['ports'])
        yield hs.add_to_tor(proto)
        print("Created HS", hs.hostname)

        def remove():
            print("removing hidden-service")
            return hs.remove_from_tor(proto)
        reactor.addSystemEventTrigger('before', 'shutdown', remove)

        print("...waiting for descriptor upload")
        yield got_upload
        print("Got one.", time.asctime())

        # we never callback() on this, so we serve forever
        d = Deferred()
        yield d

    def _remove_service(self, config, hs):
        print("removing " + hs)
        config.hiddenservices.remove(hs)
        return config.save()

# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = TempHSCommand()
