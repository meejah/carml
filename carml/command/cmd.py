#
# FIXME: better name? "the command called cmd" is pretty weird
#

from __future__ import print_function

import os
import sys
import functools

import zope.interface
from twisted.python import usage, log
from twisted.protocols.basic import LineReceiver
from twisted.internet import defer, reactor, stdio

import txtorcon
from carml.interface import ICarmlCommand
from carml import util


class CmdOptions(usage.Options):
    def __init__(self):
        super(CmdOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')
        self.args = None

    def parseArgs(self, *args):
        self.args = args

    def getUsage(self, **kw):
        return "Options:\n   Pass any number of strings as args, which will be executed as a Tor controller command and the result printed. Pass a single dash (-) to read commands from stdin a line at a time."


class StdioLineReceiver(LineReceiver):
    delimiter = '\n'

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
        d = do_cmd(self.proto, tuple(keys))
        d.addCallback(self._completed, d)
        d.addErrback(self._error, d)
        self.outstanding.append(d)

    def _error(self, arg, d):
        print(util.colors.red(str(arg)))
        return

    def _completed(self, arg, d):
        self.outstanding.remove(d)
        if self._exit and len(self.outstanding) == 0:
            self.all_done.callback(None)

    def connectionLost(self, reason):
        if len(self.outstanding):
            self._exit = True
        else:
            self.all_done.callback(None)


def do_cmd(proto, args):
    def _print(res):
        print(res)

    def _error(arg):
        print(util.colors.red(arg.getErrorMessage()))
        return None
    d = proto.queue_command(' '.join(args))
    d.addCallback(_print)
    d.addErrback(_error)
    return d


# see cmd_info for an alternate way to implement this via a method
# with attributes and "zope.interface.implementsDirectly()"
# trying out both ways to see what feels better
@zope.interface.implementer(ICarmlCommand)
class CmdSubCommand(object):
    # Attributes specified by ICarmlCommand
    name = 'cmd'
    help_text = 'Run the rest of the args as a Tor control command. For example "GETCONF SocksPort" or "GETINFO net/listeners/socks".'
    controller_connection = True
    build_state = False
    options_class = CmdOptions

    def validate(self, options, mainoptions):
        if not options.args:
            raise RuntimeError("Need to specify a command (or - to read commands from stdin).")

    @defer.inlineCallbacks
    def run(self, options, mainoptions, proto):
        """
        ICarmlCommand API
        """

        if options.args == ('-',):
            all_done = defer.Deferred()
            stdio.StandardIO(StdioLineReceiver(all_done, proto))
            yield all_done
        else:
            yield do_cmd(proto, options.args)

cmd = CmdSubCommand()
__all__ = ['cmd']
