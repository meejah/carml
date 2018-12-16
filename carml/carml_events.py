import os
import sys
import time
import functools

import zope.interface
from twisted.python import usage, log
from twisted.internet import defer, reactor

import txtorcon

from carml.util import dump_circuits
from carml.util import format_net_location
from carml.util import nice_router_name
from carml.util import colors

import click


async def run(reactor, cfg, tor, list_events, once, show_event, count, events):
    all_events = await tor.protocol.get_info('events/names')
    all_events = all_events['events/names']
    if list_events:
        for e in all_events.split():
            click.echo(e)
        return

    all_done = defer.Deferred()
    counter = [count]
    if once:
        counter[0] = 1

    def _got_event(evt, msg):
        if counter[0] is not None:
            counter[0] -= 1
            if counter[0] >= 0:
                print(msg)
            elif all_done:
                all_done.callback(None)
                all_done = None
        elif evt:
            print("{}: {}".format(evt, msg))
        else:
            ts = time.asctime()
            print("{} {}".format(ts, msg))
        sys.stdout.flush()

    for e in events:
        e = e.upper()
        if e not in all_events:
            print("Invalid event:", e)
            return
        if show_event:
            listener = functools.partial(_got_event, e)
        else:
            listener = functools.partial(_got_event, None)
        tor.protocol.add_event_listener(e, listener)

    # might be forever if there's no count
    await all_done
