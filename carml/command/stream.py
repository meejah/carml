from __future__ import print_function

import os
import sys
import functools

from twisted.python import usage, log
from twisted.internet import defer, reactor
from zope.interface import implementer
import txtorcon
import humanize

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
        ('follow', 'f', 'Follow stream creation.'),
        # ('per-process', 'p', 'Attach all new streams to one circuit, per PID.'),
    ]

    optParameters = [
        ('attach', 'a', 0, 'Attach all new streams to a particular circuit-id.', int),
        ('close', 'd', 0, 'Delete/close a stream by its ID.', int),
    ]


def attach_streams_per_process(state):
    print("Exiting (e.g. Ctrl-C) will cause Tor to resume choosing circuits.")
    print("Giving each new PID we see its own Circuit (until they're gone).")

    @implementer(txtorcon.IStreamAttacher)
    class Attacher(object):

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
    try:
        circ = state.circuits[circid]
    except KeyError:
        print("Circuit {} doesn't exist.".format(circid))
        return None
    print("Exiting (e.g. Ctrl-C) will cause Tor to resume choosing circuits.")
    print("Attaching all new streams to Circuit %d." % circ.id)
    print("   ", '->'.join([p.name if p.name_is_unique else ('~%s' % p.name) for p in circ.path]))

    @implementer(txtorcon.IStreamAttacher)
    class Attacher(txtorcon.CircuitListenerMixin):

        def circuit_closed(self, this_circ, **kw):
            if circ == this_circ:
                print("Circuit {} vanished (REASON={}, REMOTE_REASON={})".format(
                    circ.id,
                    kw.get('REASON', 'not specified'),
                    kw.get('REMOTE_REASON', 'not specified'),
                ))
                # should we just exit now?
                # Pro: kind-of makes sense
                # Con: if you're expecting streams to go via "your"
                # circuit, maybe you want them to "fail closed" and
                # not work at all -- which is what I'm doing right now
                # so -> probably want exiting to be an option, and not the default

        def attach_stream(self, stream, circuits):
            if circ.state == 'CLOSED':
                print("  target circuit is closed, not attaching")
                return txtorcon.TorState.DO_NOT_ATTACH
            if stream.state == 'NEWRESOLVE':
                print("  attaching %d (resolve %s)" % (stream.id, stream.target_host))
            else:
                print("  attaching %d %s:%d" % (stream.id, stream.target_host,
                                                stream.target_port))
            return circ

    attacher = Attacher()
    state.set_attacher(attacher, reactor)
    state.add_circuit_listener(attacher)
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


class StreamBandwidth(object):
    """
    The bandwidth-events of a single stream
    """
    #__slots__ = ['_events']

    def __init__(self, max_live=20, roll_up=5):
        self._events = []  # list of 3-tuples
        self._history = []
        self.max_live = max_live
        self.roll_up = roll_up

        # XXX we could recursively roll-up too, i.e. spill from one
        # bucket to the next. but, for now, there are precisely two
        # bucks: the "current", and the first one containing (avg,
        # min, max) etc

    def add_bandwidth(self, epoch, read, write):
        self._events.append((epoch, read, write))
        self._maybe_truncate()

    def _maybe_truncate(self):
        """
        If we've gone past our max_live amount by at least roll_up events,
        we push it into the history (possibly also truncating that).
        """
        # XXX should we examine seconds here instead? i.e. have a
        # max-seconds (instead of going by event-count)?
        if len(self._events) > self.max_live + self.roll_up:
            rolling = self._events[:self.roll_up]
            self._events = self._events[self.roll_up:]
            duration = float(self._events[0][0] - rolling[0][0])
            mean_r = sum(x[1] for x in rolling) / duration
            mean_w = sum(x[2] for x in rolling) / duration

            # XXX should append some smarter-er object instead of tuple?
            # (start, duration, mean_r, mean_w, max_r, max_w)
            self._history.append(
                (
                    rolling[0][0],
                    duration,
                    mean_r, mean_w,
                    max(x[1] for x in rolling),
                    max(x[2] for x in rolling),
                )
            )
            self._history = self._history[-10:]
            print("HISTORY NOW", self._history)
            print("age {}, total bw {}".format(
                self._events[-1][0] - (self._history[-1][0] + self._history[-1][1]),
                sum([sum(x[1:]) for x in self._history]),
            ))

    def bytes_read(self):
        return sum(event[1] for event in self._events)

    def bytes_written(self):
        return sum(event[2] for event in self._events)

    def duration(self):
        if not self._events:
            return 0.0
        if len(self._events) == 1:
            return 1.0
        return float(self._events[-1][0] - self._events[0][0]) + 1.0

    def rate(self):
        span = self.duration()
        if span == 0.0:
            return (0.0, 0.0)  # mmm...pragmatism
        return (self.bytes_read() / span, self.bytes_written() / span)


class BandwidthMonitor(txtorcon.StreamListenerMixin):
    @staticmethod
    @defer.inlineCallbacks
    def create(reactor, state):
        bw = BandwidthMonitor(reactor, state)
        yield bw._setup()
        defer.returnValue(bw)

    def __init__(self, reactor, state):
        self._reactor = reactor  # just IReactorClock required?
        self._state = state
        self._active = {}  # maps stream ID -> list-of-tuples

    def stream_new(self, stream):
        print("new", stream)
        self._active[stream.id] = StreamBandwidth()

    def stream_succeeded(self, stream):
        # i think this happens when it *starts* passing data?
        print("succeeded", stream, stream.target_host, stream.target_addr)
        try:
            print("BOOM:", self._state.addrmap.find(stream.target_host).name)
        except KeyError:
            print("unfound", stream.target_host)

    def stream_attach(self, stream, circuit):
        pass #print("attach", stream)

    def stream_detach(self, stream, **kw):
        pass #print("detach", stream)

    def stream_closed(self, stream, **kw):
        # print("closed", stream, self._active)
        if not stream.id in self._active:
            print(
                "Previously unknown stream to {stream.target_host} died".format(
                    stream=stream,
                )
            )
        else:
            bw = self._active[stream.id]
            print(
                "Stream {stream.id} to {stream.target_host}: {read} read, {written} written in {duration:.1f}s ({read_rate})".format(
                    stream=stream,
                    read=util.colors.green(humanize.naturalsize(bw.bytes_read())),
                    written=util.colors.red(humanize.naturalsize(bw.bytes_written())),
                    read_rate=humanize.naturalsize(sum(bw.rate())) + '/s',
                    duration=bw.duration(),
                )
            )

    def stream_failed(self, stream, **kw):
        pass

    def _stream_bw(self, bw):
        #print("STREAM BW", bw)
        sid, wr, rd = [int(x) for x in bw.split()]
        try:
            bandwidth = self._active[sid]
        except KeyError:
            bandwidth = self._active[sid] = StreamBandwidth()
        bandwidth.add_bandwidth(self._reactor.seconds(), rd, wr)

    @defer.inlineCallbacks
    def _setup(self):
        yield self._state.add_stream_listener(self)
        yield self._state.protocol.add_event_listener('STREAM_BW', self._stream_bw)


@defer.inlineCallbacks
def monitor_streams(state, verbose):
    print("monitor", state, verbose)
    from twisted.internet import reactor
    bw = yield BandwidthMonitor.create(reactor, state)


@implementer(ICarmlCommand)
class StreamCommand(object):

    # Attributes specified by ICarmlCommand
    name = 'stream'
    options_class = StreamOptions
    help_text = 'Manipulate Tor streams.'
    controller_connection = True
    build_state = True

    def validate(self, options, mainoptions):
        cmds = ['attach', 'list', 'close', 'follow']  # , 'per-process']
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
        elif options['follow']:
            d = defer.succeed(None)
            d.addCallback(lambda _: monitor_streams(state, verbose))
            d.addCallback(lambda _: defer.Deferred())
            return d

        reactor.stop()

cmd = StreamCommand()
__all__ = ['cmd']
