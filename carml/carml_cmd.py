#
# FIXME: better name? "the command called cmd" is pretty weird
#
import os
import sys
import functools

import zope.interface
from twisted.python import usage, log
from twisted.protocols.basic import LineReceiver
from twisted.internet import defer, reactor, stdio

import txtorcon
from carml import util


class StdioLineReceiver(LineReceiver):
    # note: for python3, if this isn't bytes, nothing works but
    # Twisted doesn't tell you that ( or eats the error?)
    delimiter = b'\n'

    def __init__(self, all_done, proto):
        self.proto = proto
        self.all_done = all_done
        self.outstanding = []
        self._exit = False      # when True, all_done.callback() when outstanding empties

    def connectionMade(self):
        print("Keep entering keys to run CMD on. Control-d to exit.", file=sys.stderr)

    def lineReceived(self, line):
        # Ignore blank lines
        if not line:
            return
        keys = line.split()
        # we really do want this to be a Deferred because lineReceived
        # isn't (can't be) an async method..
        token = object()
        self.outstanding.append(token)
        d = defer.ensureDeferred(do_cmd(self.proto, tuple(keys)))
        d.addCallback(self._completed, token)
        d.addErrback(self._error, token)

    def _error(self, arg, token):
        print(util.colors.red(str(arg)))
        self.outstanding.remove(token)
        return

    def _completed(self, arg, token):
        self.outstanding.remove(token)
        if self._exit and len(self.outstanding) == 0:
            self.all_done.callback(None)

    def connectionLost(self, reason):
        if len(self.outstanding):
            self._exit = True
        else:
            self.all_done.callback(None)


def ensure_bytes(x):
    if isinstance(x, bytes):
        return x
    return x.encode('ascii')


async def do_cmd(proto, args):
    bytes_args = [
        ensure_bytes(b)
        for b in args
    ]
    try:
        # command must be in bytes
        res = await proto.queue_command(b' '.join(bytes_args))
        print(res)
    except Exception as e:
        print(util.colors.red(str(e)))


# see cmd_info for an alternate way to implement this via a method
# with attributes and "zope.interface.implementsDirectly()"
# trying out both ways to see what feels better
async def run(reactor, cfg, tor, args):
    if len(args) == 0:
        print("(no command to run)")

    elif len(args) == 1 and args[0] == '-':
        all_done = defer.Deferred()
        stdio.StandardIO(StdioLineReceiver(all_done, tor.protocol))
        await all_done
    else:
        await do_cmd(tor.protocol, args)
