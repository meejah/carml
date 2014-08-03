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


class HelpOptions(usage.Options):
    def __init__(self):
        super(HelpOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')
        self.what = None

    def parseArgs(self, *args):
        self.what = args[0] if len(args) else None

    def getUsage(self, **kw):
        return "Options:\n   Pass a single sub-command to print help for."


@zope.interface.implementer(ICarmlCommand)
class HelpSubCommand(object):
    # Attributes specified by ICarmlCommand
    name = 'help'
    help_text = 'Print help on sub-commands (like "carml help events").'
    controller_connection = False
    build_state = False
    options_class = HelpOptions

    def validate(self, options, mainoptions):
        pass

    def run(self, options, mainoptions, proto):
        """
        ICarmlCommand API
        """

        w = options.what
        if w is None:
            from carml.dispatch import Options
            print(Options().getUsage())
            return
            for sub in mainoptions.commands.values():
                print('## %s\n%s\n' % (sub.name, ('-' * (3 + len(sub.name)))))
                print_help_for(sub)
            return

        try:
            print('Sub-command "%s":' % w)
            print_help_for(mainoptions.commands[w])
        except KeyError:
            print('Unknown command "%s".' % w)
        return defer.succeed(None)


def print_help_for(sub):
    desc = util.wrap(sub.help_text, 60, '    ')
    print(desc)
    for line in sub.options_class().getUsage().split('\n'):
        print('    ', line)


cmd = HelpSubCommand()
__all__ = ['cmd']
