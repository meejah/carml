from __future__ import print_function

import os
import sys
import functools

import zope.interface
from twisted.python import usage, log, failure
from twisted.internet import defer, reactor, error
import humanize

import txtorcon

from carml.interface import ICarmlCommand
from carml.util import dump_circuits, format_net_location, nice_router_name, colors, wrap

LOG_LEVELS = ["DEBUG", "INFO", "NOTICE", "WARN", "ERR"]


class MonitorOptions(usage.Options):
    optFlags = [
        ('once', 'o', 'Exit after printing the current state.'),
        ('no-streams', 's', 'Without this, list Tor streams.'),
        ('no-circuits', 'c', 'Without this, list Tor circuits.'),
        ('no-addr', 'a', 'Without this, list address mappings (and expirations, with -f).'),
        ('no-guards', 'g', 'Without this, Information about your current Guards.'),
        ('verbose', 'v', 'Additional information. Circuits: ip, location, asn, country-code.'),
    ]

    optParameters = [
        ('log-level', 'l', 'INFO', 'Subscribe to Tor log messages up to "level". Valid levels are: %s' % ' '.join(LOG_LEVELS)),
    ]

    def opt_log_level(self, x):
        if x.lower() == 'all':
            self['log-level'] = LOG_LEVELS

        levels = x.upper()
        if ',' in x:
            levels = levels.split(',')
        else:
            levels = [levels]

        for sub in levels:
            if sub not in LOG_LEVELS:
                raise RuntimeError('Unknown log level "%s".' % sub)
        self['log-level'].extend(levels)

    def __init__(self):
        """
        We override this to get rid of the Twisted default --version and --help things
        """
        super(MonitorOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')
        self['log-level'] = []


def string_for_circuit(state, circuit):
    # path = '->'.join(map(lambda x: x.location.countrycode or '??', circuit.path))
    path = '->'.join(map(lambda x: x.name, circuit.path))
    state = circuit.state
    if state.lower() == 'failed':
        state = colors.red(state)
    return 'Circuit %d (%s) is %s for purpose "%s"' % (circuit.id, path, state, circuit.purpose)


def string_for_stream(state, stream):
    circ = ''
    if stream.circuit:
        circ = ' via circuit %d' % stream.circuit.id
    proc = txtorcon.util.process_from_address(stream.source_addr, stream.source_port, state)
    if proc:
        proc = ' from process "%s"' % (colors.bold(os.path.realpath('/proc/%d/exe' % proc)), )

    elif stream.source_addr == '(Tor_internal)':
        proc = ' for Tor internal use'

    elif stream.source_addr:
        proc = ' from remote "%s:%s"' % (str(stream.source_addr), str(stream.source_port))

    else:
        proc = ''
    hoststring = colors.bold('%s:%d' % (stream.target_host, stream.target_port))
    return 'Stream %d to %s %s%s%s' % (stream.id, hoststring, colors.green('attached'), circ, proc)


class StreamLogger(txtorcon.StreamListenerMixin):
    def __init__(self, state, verbose):
        self.state = state
        self.verbose = verbose

    def stream_attach(self, stream, circuit):
        print(string_for_stream(self.state, stream))
        if self.verbose:
            m = "  " + '->'.join(map(lambda x: nice_router_name(x), circuit.path))
            m += ' (%s)' % ' '.join(map(lambda r: str(r.location.countrycode), circuit.path))
            print(m)

    def stream_failed(self, stream, remote_reason='', **kw):
        print('Stream %d %s because "%s"' % (stream.id, colors.red('failed'),
                                             colors.red(remote_reason)))


def flags(d):
    """
    Basically converts a dict into name=value string, but only if the
    key is all-uppercase. This is because of the way we re-map keyword
    args for the circuit listeners, etcetra.
    """

    r = ''
    for (k, v) in d.iteritems():
        if k.upper() == k:
            r += '%s=%s ' % (k, v)
    return r


class CircuitLogger(txtorcon.CircuitListenerMixin):
    def __init__(self, state, show_flags=False):
        self.state = state
        self.show_flags = show_flags

    def circuit_launched(self, circuit):
        print(string_for_circuit(self.state, circuit))

    def circuit_extend(self, circuit, router):
        print(string_for_circuit(self.state, circuit))

    def circuit_built(self, circuit):
        print(string_for_circuit(self.state, circuit))
        if self.show_flags:
            flagslist = ['%s=%s' % x for x in circuit.flags.items()]
            flags = wrap(' '.join(flagslist), 72, '    ')
            print(colors.cyan('    Flags:'), flags.lstrip())

    def circuit_failed(self, circuit, **kw):
        print('Circuit %d failed (%s).' % (circuit.id, flags(kw)))

    def circuit_closed(self, circuit, **kw):
        print('Circuit %d %s lasted %s (%s).' % (circuit.id,
                                                 colors.red('closed'),
                                                 humanize.time.naturaldelta(circuit.age()),
                                                 flags(kw)))


class AddressLogger(object):
    zope.interface.implements(txtorcon.interface.IAddrListener)

    def addrmap_added(self, addr):
        print('New address mapping: "%s" -> "%s".' % (addr.name, addr.ip))

    def addrmap_expired(self, name):
        print('Address mapping for "%s" expired.' % name)


def tor_log(level, msg):
    print('%s: %s' % (level, msg))


def monitor_callback(options, state):
    follow_string = None
    if options['log-level'] and not options['once']:
        follow_string = 'Logging ('
        for event in options['log-level']:  # LOG_LEVELS:
            state.protocol.add_event_listener(event, functools.partial(tor_log, event))
            follow_string += event + ', '
            if event == options['log-level']:
                break
        follow_string = follow_string[:-2] + ')'
    if not options['no-streams']:
        if follow_string:
            follow_string += ' and Stream'
        else:
            follow_string = 'Stream'
        if len(state.streams):
            print("Current streams:")
            for stream in state.streams.values():
                print('  ' + string_for_stream(state, stream))
        else:
            print("No streams.")
        state.add_stream_listener(StreamLogger(state, options['verbose']))

    if not options['no-circuits']:
        if follow_string:
            follow_string += ' and Circuit'
        else:
            follow_string = 'Circuit'

        if len(state.circuits):
            print("Current circuits:")
            dump_circuits(state, verbose=options['verbose'])
        else:
            print("No circuits.")
        state.add_circuit_listener(CircuitLogger(state, show_flags=options['verbose']))

    if not options['no-guards']:
        if len(state.entry_guards):
            print("Current Entry Guards:")
            for (name, router) in state.entry_guards.iteritems():
                if not router.from_consensus:
                    if router.name:
                        print("  %s: %s (not in consensus)" % (router.name, router.id_hex))
                    else:
                        print("  %s (not in consensus)" % router.id_hex)

                else:
                    print(" ", router.id_hex, router.name, format_net_location(router.location))

        else:
            print("No Guard nodes!")

    if not options['no-addr']:
        if follow_string:
            follow_string += ' and Address'
        else:
            follow_string = 'Address'

        if len(state.addrmap.addr):
            print("Current address mappings:")
            for addr in state.addrmap.addr.values():
                print('  %s -> %s' % (addr.name, addr.ip))
            state.addrmap.add_listener(AddressLogger())
        else:
            print("No address mappings.")

    all_done = defer.Deferred()
    if not options['once']:
        print('')
        print("Following new %s activity:" % follow_string)

        def stop_reactor(arg):
            print("Tor disconnected.")
            all_done.callback(None)
        def error(fail):
            print(colors.red('Error:'), fail.getErrorMessage())
        state.protocol.on_disconnect.addErrback(error).addBoth(stop_reactor)

    else:
        all_done.callback(None)
    return all_done


class MonitorCommand(object):
    zope.interface.implements(ICarmlCommand)

    name = 'monitor'
    help_text = """General information about a running Tor; streams, circuits, address-maps and event monitoring."""
    controller_connection = True
    build_state = True
    options_class = MonitorOptions

    def validate(self, options, mainoptions):
        return
        at_least_one = False
        for k in ['streams', 'circuits', 'addr']:
            if options[k]:
                at_least_one = True
                break
        if not at_least_one and not (options['guards'] or options['log-level']):
            raise RuntimeError("Must specify at least one of --streams, --circuits, "
                               "--guards or --addr or --log-level")
        if not options['once'] and not (at_least_one or options['log-level']):
            raise RuntimeError("Can't follow just guards updates; add --once or exclude "
                               " fewer things.")
        if options['log-level'] and options['once']:
            raise RuntimeError("--log-level with --once doesn't make sense.")

    def run(self, options, mainoptions, state):
        return monitor_callback(options, state)


cmd = MonitorCommand()
__all__ = ['cmd']
