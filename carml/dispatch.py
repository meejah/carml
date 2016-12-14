from __future__ import print_function

import os
import sys
import time
import functools

from twisted.python import usage, log
from twisted.internet import reactor, defer, endpoints, task
from zope.interface import implements
import txtorcon

from carml.interface import ICarmlCommand
import carml.util as util
import carml


class LogObserver(object):
    def __init__(self, timestamp=False, flush=True):
        self.timestamp = timestamp
        self.flush = flush
        # we keep our own copies of these, because Twisted's
        # startLoggingWithObserver overwrites them with its own
        # monitoring machinery
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def __call__(self, arg):
        # we don't want to print out every little thing logged by
        # Twisted or txtorcon, just what we output (which is always
        # print()-ed)
        try:
            if not arg['printed']:
                return
        except KeyError:
            return
        msg = ' '.join(arg['message'])

        # possibly add timestamps
        if self.timestamp:
            msg = util.colors.cyan(time.asctime()) + ': ' + msg

        # figure out if we want stdout or stderr
        out = self.stdout
        if 'isError' in arg and arg['isError']:
            out = self.stderr
            if not msg and 'failure' in arg:
                msg = util.colors.red('Error: ') + arg['failure'].getErrorMessage()

        # actually print message
        print(msg, file=out)
        if self.flush:
            out.flush()

_log_observer = LogObserver()
log.startLoggingWithObserver(_log_observer, setStdout=False)


class Options(usage.Options):
    """
    command-line options we understand
    """

    color_options = ['auto', 'always', 'never']

    def opt_version(self):
        "Display version and exit."
        print('carml version', carml.__version__)
        sys.exit(0)

    # these are all on/off
    optFlags = [
        ('timestamps', 't', 'Prepend timestamps to each line.'),
        ('no-color', 'n', 'Same as --color=no.'),
        ('info', 'i', 'Show version of Tor we connect to (on stderr).'),
        ('quiet', 'q', 'Some commands show less information with this option.'),
        ('debug', 'd', 'Debug; print stack traces on error.'),
    ]

    # these take options, sometimes with defaults
    optParameters = [
        ('password', 'p', None, 'Password to authenticate to Tor with. Cookie-based authentication is much easier if you are on the same machine.', str),
        ('connect', 'c', 'tcp:host=127.0.0.1:port=9051', 'Where to connect to Tor. This accepts any Twisted client endpoint string, or an ip:port pair. Examples: "tcp:localhost:9151" or "unix:/var/run/tor/control".', str),
        ('color', 'C', 'auto', 'Colourize output using ANSI commands. auto, no, always', str),
    ]

    # these are dynamically discovered via IPlugin machinery; see below.
    subCommands = []

    def __init__(self):
        super(Options, self).__init__()

        from twisted.plugin import getPlugins
        # this is some Twisted boilerplate so we can have
        # "carml/command" for our plugin path.
        from carml import command

        # we discover any ICarmlCommand implementations, including the
        # built-in commands; for more about this, see:
        # http://twistedmatrix.com/documents/current/core/howto/plugin.html
        self.commands = {}
        for cmd in getPlugins(ICarmlCommand, command):
            self.subCommands.append((cmd.name, None, cmd.options_class, cmd.help_text))
            self.commands[cmd.name] = cmd

    def postOptions(self):
        if self['no-color']:
            self['color'] = 'never'
        if self['color'] not in self.color_options:
            print("--color accepts one of: ", ', '.join(self.color_options))
            sys.exit(2)


@defer.inlineCallbacks
def general_information(proto_or_state, verbose):
    """
    Since commands that either build or don't-build a TorState object
    both use this, we accept either.
    """

    # FIXME maybe use the interfaces instead?
    if hasattr(proto_or_state, 'protocol'):
        proto = proto_or_state.protocol
    else:
        proto = proto_or_state
    info = yield proto.get_info('version', 'status/version/current', 'dormant')
    if info['status/version/current'] != 'recommended' or verbose:
        sys.stderr.write('Connected to a Tor version "%(version)s" (status: %(status/version/current)s).\n' % info)
    if int(info['dormant']):
        msg = util.colors.red("(This Tor is dormant).\n")
        sys.stderr.write(msg)
    defer.returnValue(proto_or_state)


def setup_failed(e, debug):
    print(util.colors.red('Error: ') + e.getErrorMessage(), file=sys.stderr)
    if debug:
        e.printTraceback(file=sys.stderr)
    # twisted seems to get grumpy if you do reactor.stop inside an
    # errback.
    reactor.callLater(0, reactor.stop)


def dispatch(args=None):
    """
    this is the main program; see __main__.py
    """

    if args is None:
        args = sys.argv

    global _log_observer
    options = Options()

    try:
        options.parseOptions(args[1:])

    except (usage.UsageError, RuntimeError) as e:
        print(options.getUsage())
        print(util.colors.red('Error: ') + str(e), file=sys.stderr)
        sys.exit(128)

    except Exception as e:
        print('Unknown error:', e)
        sys.exit(200)

    if options['color'] == 'never' or options['no-color'] or \
            (options['color'] == 'auto' and not sys.stdin.isatty()):
        util.turn_off_color()

    if options.subCommand is None:
        print(options)
        return

    sub = options.commands[options.subCommand]

    try:
        sub.validate(options.subOptions, options)
    except Exception as e:
        print(options.getUsage())
        print(util.colors.red('Error: ') + str(e), file=sys.stderr)
        if options['debug']:
            raise e
        return

    build_state = sub.build_state
    show_general_info = options['info']

    endpoint_str = os.environ.get("TOR_CONTROL_PORT", None)
    if endpoint_str is None:
        endpoint_str = options['connect']
    try:
        endpoint = endpoints.clientFromString(reactor, endpoint_str)
    except ValueError:
        try:
            endpoint = endpoints.clientFromString(reactor, 'tcp:' + options['connect'])
        except TypeError:
            endpoint = endpoints.clientFromString(reactor, 'tcp:localhost:' + options['connect'])

    if options['timestamps']:
        _log_observer.timestamp = True

    if sub.controller_connection:
        d = txtorcon.build_tor_connection(endpoint, build_state=build_state)
    elif sub.build_state:
        raise RuntimeError("Internal error: subcommand can't set build_state=True with controller_connection=False")
    else:
        d = defer.succeed(None)
        show_general_info = False

    if show_general_info:
        d.addCallback(general_information, True)

    d.addCallback(lambda arg: ICarmlCommand(sub).run(options.subOptions, options, arg))
    d.addErrback(setup_failed, options['debug'])

    if options['debug']:
        def dump_heap():
            from guppy import hpy
            print(hpy().heap())
        d.addCallback(lambda _: dump_heap())

    # task.react needs a function that returns a Deferred
    task.react(lambda _: d)
