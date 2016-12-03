from __future__ import print_function

import os
import sys
import functools

import zope.interface
from twisted.python import usage, log, failure
from twisted.internet import defer, reactor, error
import humanize

import txtorcon

from twisted.internet.defer import inlineCallbacks, Deferred

from carml.interface import ICarmlCommand
from carml.util import dump_circuits, format_net_location, nice_router_name, colors, wrap

LOG_LEVELS = ["DEBUG", "INFO", "NOTICE", "WARN", "ERR"]


class GraphOptions(usage.Options):
    optFlags = [
    ]

    optParameters = [
        ('max', 'm', 1024*20, 'Maximum scale, in bytes.', int)
    ]

    def __init__(self):
        """
        We override this to get rid of the Twisted default --version and --help things
        """
        super(GraphOptions, self).__init__()
        self.longOpt.remove('version')
        ##self.longOpt.remove('help')

class BandwidthTracker(object):
    '''
    This tracks bandwidth usage.
    '''

    def __init__(self, maxscale, state):
        #: a list of tuples
        self._bandwidth = []
        self._max = float(maxscale)
        self._state = state

    def circuits(self):
        return len(self._state.circuits)

    def streams(self):
        return len(self._state.streams)

    def on_bandwidth(self, s):
        r, w = map(int, s.split())
        self._bandwidth.append((r, w))
        self.draw_bars()

    def on_stream_bandwidth(self, s):
        #print("stream", s)
        pass

    def draw_bars(self):
        up = min(1.0, self._bandwidth[-1][0] / self._max)
        dn = min(1.0, self._bandwidth[-1][1] / self._max)
        kbup = self._bandwidth[-1][1] / 1024.0
        kbdn = self._bandwidth[-1][0] / 1024.0

        status = ' ' + colors.green('%.2f' % kbdn)
        status += '/'
        status += colors.red('%.2f' % kbup) # + ' KiB write'
        status += ' KiB/s'
        status += ' (%d streams, %d circuits)' % (self.streams(), self.circuits())

        # include the paths of any currently-active streams
        streams = ''
        for stream in self._state.streams.values():
            # ...there's a window during which it may not be attached yet
            if stream.circuit:
                circpath = '>'.join(map(lambda r: r.location.countrycode, stream.circuit.path))
                streams += ' ' + circpath
        if len(streams) > 24:
            streams = streams[:21] + '...'
        print(left_bar(up, 20) + unichr(0x21f5) + right_bar(dn, 20) + status + streams)



def left_bar(percent, width):
    '''
    Creates the green/left bar from a percentage and width. It uses
    some unicode vertical-bar characters to get some extra precision
    on the bar-length.
    '''
    blocks = int(percent * width)
    remain = (percent * width) - blocks

    part = int(remain * 8)
    rpart = unichr(0x258f - 7 + part) # for smooth bar

    return (' ' * (width - blocks)) + colors.negative(colors.green(rpart)) + colors.green(('+' * (blocks)), bg='green')

def right_bar(percent, width):
    '''
    See left_bar(); inverse and in red instead.
    '''
    blocks = int(percent * width)
    remain = (percent * width) - blocks

    part = int(remain * 8)
    rpart = unichr(0x258f - part) # for smooth bar
    if part == 0:
        rpart = ' '

    return colors.red('+' * (blocks), bg='red') + (colors.red(rpart)) + (' ' * (width - blocks))

@inlineCallbacks
def main(options, state):
    proto = state.protocol
    bwtracker = BandwidthTracker(options['max'], state)
    yield proto.add_event_listener('BW', bwtracker.on_bandwidth)
    yield proto.add_event_listener('STREAM_BW', bwtracker.on_stream_bandwidth)

    # infinite loop
    yield Deferred()


class GraphCommand(object):
    zope.interface.implements(ICarmlCommand)

    name = 'graph'
    help_text = 'A nice coloured console bandwidth-graph.'
    controller_connection = True
    build_state = True
    options_class = GraphOptions

    def validate(self, options, mainoptions):
        pass

    def run(self, options, mainoptions, state):
        return main(options, state)


cmd = GraphCommand()
__all__ = ['cmd']
