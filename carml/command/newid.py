from __future__ import print_function

import sys
import functools

import zope.interface
from twisted.python import usage, log
from twisted.internet import defer, reactor

from carml.interface import ICarmlCommand


class NewidOptions(usage.Options):
    def __init__(self):
        super(NewidOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')


def newid_got_signal(all_done, x):
    if x == 'NEWNYM':
        print('success.')
        all_done.callback(None)


def newid_no_signal(left, all_done):
    if left > 0:
        print('Waiting %d more seconds.' % left)
        reactor.callLater(1, newid_no_signal, left - 1, all_done)
    else:
        all_done.errback(RuntimeError('no acknowledgement in 10 seconds.'))


@zope.interface.implementer(ICarmlCommand)
class NewidCommand(object):
    # Attributes specified by ICarmlCommand
    name = 'newid'
    help_text = 'Ask Tor for a new identity via NEWNYM, and listen for the response acknowledgement.'
    controller_connection = True
    build_state = False
    options_class = NewidOptions

    def validate(self, options, mainoptions):
        return

    @defer.inlineCallbacks
    def run(self, options, mainoptions, proto):
        all_done = defer.Deferred()

        # Tor emits this event whenever it processes a SIGNAL command.
        proto.add_event_listener('SIGNAL', functools.partial(newid_got_signal, all_done))

        print("Requesting new identity",)
        sys.stdout.flush()
        yield proto.signal('NEWNYM')
        # answer will be "OK" since Tor received the signal
        # if rate-limiting is happening, the "SIGNAL NEWNYM" event
        # will not be received. so we wait for it
        reactor.callLater(1, newid_no_signal, 10, all_done)
        yield all_done

cmd = NewidCommand()
__all__ = ['cmd']
