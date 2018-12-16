import os
import sys
import functools

import zope.interface
from twisted.python import usage, log, failure
from twisted.internet import defer, reactor, error
import humanize

import txtorcon

from carml.util import dump_circuits, format_net_location, nice_router_name, colors, wrap

LOG_LEVELS = ["DEBUG", "INFO", "NOTICE", "WARN", "ERR"]


def string_for_circuit(state, circuit):
    # path = '->'.join(x.location.countrycode or '??' for x in circuit.path)
    path = '->'.join(x.name for x in circuit.path)
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
            m = "  " + '->'.join(nice_router_name(x) for x in circuit.path)
            m += ' (%s)' % ' '.join(str(r.location.countrycode) for r in circuit.path)
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
    for (k, v) in d.items():
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


@zope.interface.implementer(txtorcon.interface.IAddrListener)
class AddressLogger(object):

    def addrmap_added(self, addr):
        print('New address mapping: "%s" -> "%s".' % (addr.name, addr.ip))

    def addrmap_expired(self, name):
        print('Address mapping for "%s" expired.' % name)


def tor_log(level, msg):
    print('%s: %s' % (level, msg))


async def run(reactor, cfg, tor, verbose, no_guards, no_addr, no_circuits, no_streams, once, log_level):
    state = await tor.create_state()

    follow_string = None
    if log_level and not once:
        follow_string = 'Logging ('
        for event in log_level:  # LOG_LEVELS:
            state.protocol.add_event_listener(event, functools.partial(tor_log, event))
            follow_string += event + ', '
            if event == log_level:
                break
        follow_string = follow_string[:-2] + ')'
    if not no_streams:
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
        state.add_stream_listener(StreamLogger(state, verbose))

    if not no_circuits:
        if follow_string:
            follow_string += ' and Circuit'
        else:
            follow_string = 'Circuit'

        if len(state.circuits):
            print("Current circuits:")
            dump_circuits(state, verbose=verbose)
        else:
            print("No circuits.")
        state.add_circuit_listener(CircuitLogger(state, show_flags=verbose))

    if not no_guards:
        if len(state.entry_guards):
            print("Current Entry Guards:")
            for (name, router) in state.entry_guards.items():
                if not router.from_consensus:
                    if router.name:
                        print("  %s: %s (not in consensus)" % (router.name, router.id_hex))
                    else:
                        print("  %s (not in consensus)" % router.id_hex)

                else:
                    print(" ", router.id_hex, router.name, format_net_location(router.location))

        else:
            print("No Guard nodes!")

    if not no_addr:
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
    if not once:
        print('')
        print("Following new %s activity:" % follow_string)

        def stop_reactor(arg):
            print("Tor disconnected.")
            all_done.callback(None)

        def error(fail):
            print(colors.red('Error:'), fail.getErrorMessage())
        # use state.protocol.when_disconnected() after next txtorcon release
        state.protocol.on_disconnect.addErrback(error).addBoth(stop_reactor)

    else:
        all_done.callback(None)
    await all_done
