from __future__ import print_function

import os
import sys
import functools

from twisted.python import usage, log
from twisted.internet import defer, reactor
import zope.interface
import txtorcon

from carml.interface import ICarmlCommand
from carml import util


class StreamOptions(usage.Options):
    def __init__(self):
        super(StreamOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')
        self['delete'] = []

    optFlags = [
        ('list', 'L', 'List existing streams.'),
        # ('per-process', 'p', 'Attach all new streams to one circuit, per PID.'),
    ]

    optParameters = [
        ('attach', 'a', 0, 'Attach all new streams to a particular circuit-id.', int),
        ('close', 'd', 0, 'Delete/close a stream by its ID.', int),
    ]


def attach_streams_per_process(state):
    print("Exiting (e.g. Ctrl-C) will cause Tor to resume choosing circuits.")
    print("Giving each new PID we see its own Circuit (until they're gone).")

    class Attacher(object):
        zope.interface.implements(txtorcon.IStreamAttacher)

        def __init__(self):
            self.pid_to_circuits = {}

        def choose_new_circuit(self, stream, circuits):
            for circ in circuits.values():
                if circ in self.pid_to_circuits.values():
                    continue
                if circ.state != 'BUILT':
                    continue
                return circ
            raise RuntimeError("Ran out of circuits to select.")

        def attach_stream(self, stream, circuits):
            src_addr, src_port = stream.flags['SOURCE_ADDR'].split(':')
            pid = txtorcon.util.process_from_address(src_addr, src_port)
            procname = os.path.realpath('/proc/%d/exe' % pid)

            try:
                circ = self.pid_to_circuits[pid]
            except KeyError:
                circ = self.choose_new_circuit(stream, circuits)
                self.pid_to_circuits[pid] = circ
                print('Selected circuit %d for process %d (%s).' % (circ.id, pid, procname))
                print('  ', '->'.join([p.name if p.name_is_unique else ('{%s}' % p.name) for p in circ.path]))

#            if stream.state == 'NEWRESOLVE':
#                print "  attaching %d (resolve %s)" % (stream.id, stream.target_host)
#            else:
            print("  attaching stream %d to circuit %d for %s:%d (%s)" % (stream.id, circ.id, stream.target_host, stream.target_port, procname))
            return circ

    state.set_attacher(Attacher(), reactor)


def attach_streams_to_circuit(circid, state):
    circ = state.circuits[circid]
    print("Exiting (e.g. Ctrl-C) will cause Tor to resume choosing circuits.")
    print("Attaching all new streams to Circuit %d." % circ.id)
    print("   ", '->'.join([p.name if p.name_is_unique else ('~%s' % p.name) for p in circ.path]))

    class Attacher(object):
        zope.interface.implements(txtorcon.IStreamAttacher)

        def attach_stream(self, stream, circuits):
            if stream.state == 'NEWRESOLVE':
                print("  attaching %d (resolve %s)" % (stream.id, stream.target_host))
            else:
                print("  attaching %d %s:%d" % (stream.id, stream.target_host,
                                                stream.target_port))
            return circ

    state.set_attacher(Attacher(), reactor)
    # FIXME doesn't exit on control-c? :(
    d = defer.Deferred()
    d.addBoth(lambda x: print('foo', x))
    return d


def list_streams(state, verbose):
    print("Streams:")
    for stream in state.streams.values():
        flags = str(stream.flags) if stream.flags else 'no flags'
        state = stream.state
        state_to_color = dict(SUCCEEDED=util.colors.green,
                              FAILED=util.colors.red)
        if state in state_to_color:
            state = state_to_color[state](state)
        print("  %d: %s on circuit %d (%s)" % (stream.id, state, stream.circuit.id,
                                               flags))
        if verbose:
            h = stream.target_addr if stream.target_addr else stream.target_host
            source = txtorcon.util.process_from_address(stream.source_addr, stream.source_port)
            if source is None:
                source = 'unknown'
            print("     to %s:%s, from %s" % (h, stream.target_port, source))

    reactor.stop()


@defer.inlineCallbacks
def close_stream(state, streamid):
    class DetermineStreamClosure(object):
        def __init__(self, target_id, done_d):
            self.circ_id = str(target_id)
            self.stream_gone = False
            self.already_deleted = False
            self.completed_d = done_d

        def __call__(self, text):
            cid, what, _ = text.split(' ', 2)
            if what in ['CLOSED', 'FAILED']:
                if self.circ_id == cid:
                    self.stream_gone = True
                    print("gone (%s)..." % self.circ_id,)
                    sys.stdout.flush()
                    if self.already_deleted:
                        self.completed_d.callback(self)
    if streamid not in state.streams:
        print('No such stream "%s".' % streamid)
        return
    print('Closing stream "%s"...' % (streamid, ))

    gone_d = defer.Deferred()
    monitor = DetermineStreamClosure(streamid, gone_d)
    state.protocol.add_event_listener('STREAM', monitor)
    sys.stdout.flush()

    try:
        status = yield state.streams[streamid].close()
        status = status.state
        monitor.already_deleted = True
    except txtorcon.TorProtocolError as e:
        print(util.colors.red('Error: ') + e.what())
        return

    if monitor.stream_gone:
        print(status)
        return

    print('%s (waiting for CLOSED)...' % status)
    sys.stdout.flush()
    yield gone_d
    # we're now awaiting a callback via CIRC events indicating
    # that our stream has entered state CLOSED


class StreamCommand(object):
    zope.interface.implements(ICarmlCommand)

    # Attributes specified by ICarmlCommand
    name = 'stream'
    options_class = StreamOptions
    help_text = 'Manipulate Tor streams.'
    controller_connection = True
    build_state = True

    def validate(self, options, mainoptions):
        cmds = ['attach', 'list', 'close']  # , 'per-process']
        not_a_one = all(map(lambda x: not options[x], cmds))
        if not_a_one:
            raise RuntimeError("Specify one of: " + ', '.join(cmds))

    def run(self, options, mainoptions, state):
        """
        ICarmlCommand API
        """

        verbose = True
        if 'verbose' in options:
            verbose = options['verbose']
        if options['attach']:
            return attach_streams_to_circuit(options['attach'], state)
#        elif options['per-process']:
#            return attach_streams_per_process(state)
        elif options['list']:
            return list_streams(state, verbose)
        elif options['close']:
            d = close_stream(state, options['close'])
            d.addBoth(lambda x: reactor.stop())
            return d

        reactor.stop()

cmd = StreamCommand()
__all__ = ['cmd']
