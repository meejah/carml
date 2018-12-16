import sys
import functools

from twisted.internet import defer


def newid_got_signal(all_done, x):
    if x == 'NEWNYM':
        print('success.')
        all_done.callback(None)


def newid_no_signal(reactor, left, all_done):
    if left > 0:
        print('  waiting {} more seconds.'.format(left))
        reactor.callLater(1, newid_no_signal, reactor, left - 1, all_done)
    else:
        all_done.errback(RuntimeError('no acknowledgement in 10 seconds.'))


async def run(reactor, cfg, tor):
    all_done = defer.Deferred()

    # Tor emits this event whenever it processes a SIGNAL command.
    tor.protocol.add_event_listener('SIGNAL', functools.partial(newid_got_signal, all_done))

    print("Requesting new identity",)
    sys.stdout.flush()
    await tor.protocol.signal('NEWNYM')
    # answer will be "OK" since Tor received the signal
    # if rate-limiting is happening, the "SIGNAL NEWNYM" event
    # will not be received. so we wait for it
    reactor.callLater(1, newid_no_signal, reactor, 10, all_done)
    await all_done
