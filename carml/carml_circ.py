import sys
import datetime
import functools
import random

from twisted.python import usage, log
from twisted.internet import defer, reactor
import zope.interface
import humanize
import txtorcon

from carml import util


class CircOptions(usage.Options):
    def __init__(self):
        super(CircOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')
        self['delete'] = []

    optFlags = [
        ('list', 'L', 'List existing circuits.'),
        ('if-unused', 'u', 'When deleting, pass the IfUnused flag to Tor.'),
        ('verbose', None, 'More information per circuit.'),
    ]

    optParameters = [
        ('build', 'b', '', 'Build a new circuit, given a comma-separated list of router names or IDs. Use "auto" to let Tor select the route.', str),
    ]

    def opt_delete(self, arg):
        """Delete a circuit by its ID."""
        for x in arg.split(','):
            self['delete'].append(int(x))


async def list_circuits(reactor, cfg, tor, verbose):
    print("Circuits:")
    state = await tor.create_state()

    now = datetime.datetime.utcnow()
    util.dump_circuits(state, verbose)


async def delete_circuit(reactor, cfg, tor, circid, ifunused):
    unused_string = '(if unused) ' if ifunused else ''
    print('Deleting circuit %s"%s"...' % (unused_string, circid),)

    state = await tor.create_state()  # bootstrap=False)

    kw = {}
    if ifunused:
        kw['IfUnused'] = True

    try:
        circ = state.circuits[circid]
    except KeyError:
        raise RuntimeError("No such circuit '{}'".format(circid))

    status = await state.close_circuit(circid, **kw)
    print(status, '(waiting for CLOSED)...')
    await circ.when_closed()
    # we're now awaiting a callback via CIRC events indicating
    # that our circuit has entered state CLOSED


class _BuiltCircuitListener(txtorcon.CircuitListenerMixin):
    def __init__(self, circid, all_done):
        self.circid = circid
        self.first = True
        self._all_done = all_done

    def circuit_extend(self, circuit, router):
        if circuit.id == self.circid:
            if self.first:
                self.first = False
            else:
                sys.stdout.write(' -> ')
            sys.stdout.write(router.name)
            sys.stdout.flush()

    def circuit_built(self, circuit):
        if circuit.id == self.circid:
            print(": " + util.colors.green("built."))
            self._all_done.callback(None)

    def circuit_closed(self, circuit, **kw):
        if circuit.id == self.circid:
            print(": " + util.colors.red("closed."))
            self._all_done.callback(None)

    def circuit_failed(self, circuit, **kw):
        if circuit.id == self.circid:
            r = kw['reason'] if 'reason' in kw else ''
            rr = kw['remote_reason'] if 'remote_reason' in kw else ''
            msg = util.colors.red('failed') + ' (%s, %s).' % (r, rr)
            self._all_done.errback(RuntimeError(msg))


async def build_circuit(reactor, cfg, tor, routers):
    state = await tor.create_state()

    if len(routers) == 1 and routers[0].lower() == 'auto':
        routers = None
        # print("Building new circuit, letting Tor select the path.")
    else:
        def find_router(position, name):
            if name == '*':
                if position == 0:
                    return random.choice(list(state.entry_guards.values()))
                else:
                    return random.choice(list(state.routers.values()))
            r = state.routers.get(name) or state.routers.get('$' + name)
            if r is None:
                if len(name) == 40:
                    print("Couldn't look up %s, but it looks like an ID" % name)
                    r = name
                else:
                    raise RuntimeError('Couldn\'t find router "%s".' % name)
            return r
        routers = [
            find_router(i, r)
            for i, r in enumerate(routers)
        ]
        print("Building circuit:", '->'.join(util.nice_router_name(r) for r in routers))

    try:
        circ = await state.build_circuit(routers)
        all_done = defer.Deferred()

        sys.stdout.write("Circuit ID %d: " % circ.id)
        sys.stdout.flush()
        state.add_circuit_listener(_BuiltCircuitListener(circ.id, all_done))
        # all_done will callback when the circuit is built (or errback
        # if it fails).

    except txtorcon.TorProtocolError as e:
        log.err(e)

    await all_done


async def run(reactor, cfg, tor, if_unused, verbose, list, build, delete):
    if list:
        await list_circuits(reactor, cfg, tor, verbose)

    elif len(delete) > 0:
        deletes = []
        for d in delete:
            deletes.append(delete_circuit(reactor, cfg, tor, d, if_unused))
        results = await defer.DeferredList([defer.ensureDeferred(d) for d in deletes])
        for ok, value in results:
            if not ok:
                raise value

    elif build:
        await build_circuit(reactor, cfg, tor, build.split(','))
