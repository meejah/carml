from __future__ import print_function

import os
import sys
import time
import functools

import zope.interface
from twisted.python import usage, log
from twisted.internet import defer, reactor

import txtorcon

from carml.interface import ICarmlCommand
from carml.util import dump_circuits
from carml.util import format_net_location
from carml.util import nice_router_name
from carml.util import colors


class EventsOptions(usage.Options):
    optFlags = [
        ('list', 'L', 'Show available events.'),
        ('once', '', 'Output exactly one and quit (same as -n 1 or --count=1).'),
        ('show-event', 's', 'Prefix each line with the event it is from.'),
    ]

    optParameters = [
        ('count', 'n', None, 'Output this many events, and quit (default is unlimited).', int),
    ]

    def parseArgs(self, *args):
        self['events'] = args

    def __init__(self):
        """
        We override this to get rid of the Twisted default --version and --help things
        """
        super(EventsOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')
        self['log-level'] = []


class EventsCommand(object):
    zope.interface.implements(ICarmlCommand)

    name = 'events'
    help_text = """Follow any Tor events, listed as positional arguments."""
    controller_connection = True
    build_state = False
    options_class = EventsOptions

    def validate(self, options, mainoptions):
        if not options['list']:
            if not len(options['events']):
                raise RuntimeError("Need at least one event to watch.")

    def _got_event(self, evt, msg):
        if self.counter is not None:
            self.counter -= 1
            if self.counter >= 0:
                print(msg)
            elif self.all_done:
                self.all_done.callback(None)
                self.all_done = None
        elif evt:
            print("{}: {}".format(evt, msg))
        else:
            ts = time.asctime()
            print("{} {}".format(ts, msg))

    @defer.inlineCallbacks
    def run(self, options, mainoptions, proto):
        all_events = yield proto.get_info('events/names')
        if options['list']:
            for e in all_events['events/names'].split():
                print(e)
            return

        self.all_done = defer.Deferred()
        self.counter = options['count']
        if options['once']:
            self.counter = 1

        for e in options['events']:
            e = e.upper()
            if e not in all_events['events/names']:
                print("Invalid event:", e)
                return
            if options['show-event']:
                listener = functools.partial(self._got_event, e)
            else:
                listener = functools.partial(self._got_event, None)
            proto.add_event_listener(e, listener)

        # might be forever if there's no count
        yield self.all_done


cmd = EventsCommand()
__all__ = ['cmd']
