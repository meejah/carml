from __future__ import print_function

import sys
import datetime
import functools
import random

from twisted.python import usage, log
from twisted.internet import defer, reactor
import zope.interface
import humanize
import txtorcon

from carml.interface import ICarmlCommand
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


@defer.inlineCallbacks
def list_circuits(options, proto):
    print("Circuits:")
    state = txtorcon.TorState(proto)
    yield state.post_bootstrap

    now = datetime.datetime.utcnow()
    util.dump_circuits(state, options['verbose'])


@defer.inlineCallbacks
def delete_circuit(proto, circid, ifunused):
    # the already_deleted voodoo is because sometimes the circuit is
    # already marked as deleted before the OK comes back from the
    # controller, as in you get the event "first".
    # perhaps txtorcon should "fix"/normalize that such that it saves
    # events until the OK? maybe tor bug?
    class DetermineCircuitClosure(object):
        def __init__(self, target_id, done_deferred):
            self.circ_id = str(target_id)
            self.circuit_gone = False
            self.already_deleted = False
            self.completed = done_deferred

        def __call__(self, text):
            cid, what, _ = text.split(' ', 2)
            if what in ['CLOSED', 'FAILED']:
                if self.circ_id == cid:
                    self.circuit_gone = True
                    print("...circuit %s gone." % self.circ_id)
                    sys.stdout.flush()
                    if not self.already_deleted:
                        self.completed.callback(self)

    unused_string = '(if unused) ' if ifunused else ''
    print('Deleting circuit %s"%s"...' % (unused_string, circid),)

    gone_d = defer.Deferred()
    monitor = DetermineCircuitClosure(circid, gone_d)
    proto.add_event_listener('CIRC', monitor)
    sys.stdout.flush()

    state = txtorcon.TorState(proto, bootstrap=False)
    kw = {}
    if ifunused:
        kw['IfUnused'] = True
    try:
        status = yield state.close_circuit(circid, **kw)
        monitor.already_deleted = True
    except txtorcon.TorProtocolError as e:
        gone_d.errback(e)
        yield gone_d
        return

    if monitor.circuit_gone:
        return

    print(status, '(waiting for CLOSED)...')
    sys.stdout.flush()
    yield gone_d
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
                sys.stdout.write('->')
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


@defer.inlineCallbacks
def build_circuit(proto, routers):
    state = txtorcon.TorState(proto)
    yield state.post_bootstrap
    if len(routers) == 1 and routers[0].lower() == 'auto':
        routers = None
        # print("Building new circuit, letting Tor select the path.")
    else:
        def find_router(args):
            position, name = args
            if name == '*':
                if position == 0:
                    return random.choice(state.entry_guards.values())
                else:
                    return random.choice(state.routers.values())
            r = state.routers.get(name) or state.routers.get('$'+name)
            if r is None:
                if len(name) == 40:
                    print("Couldn't look up %s, but it looks like an ID" % name)
                    r = name
                else:
                    raise RuntimeError('Couldn\'t find router "%s".' % name)
            return r
        routers = map(find_router, enumerate(routers))
        print("Building circuit:", '->'.join(map(util.nice_router_name, routers)))

    try:
        circ = yield state.build_circuit(routers)
        all_done = defer.Deferred()

        sys.stdout.write("Circuit ID %d: " % circ.id)
        sys.stdout.flush()
        state.add_circuit_listener(_BuiltCircuitListener(circ.id, all_done))
        # all_done will callback when the circuit is built (or errback
        # if it fails).

    except txtorcon.TorProtocolError as e:
        log.err(e)

    yield all_done


class CircCommand(object):
    zope.interface.implements(ICarmlCommand)

    # Attributes specified by ICarmlCommand
    name = 'circ'
    options_class = CircOptions
    help_text = 'Manipulate Tor circuits.'
    controller_connection = True
    build_state = False

    def validate(self, options, mainoptions):
        """ICarmlCommand API"""
        if options['list'] == 0 and options['delete'] == [] and not options['build']:
            raise RuntimeError("Must specify one of --list, --delete, --build")
        if options['if-unused'] and options['delete'] == []:
            raise RuntimeError("--if-unused is only for use with --delete")

    def run(self, options, mainoptions, proto):
        """
        ICarmlCommand API
        """

        if options['list']:
            return list_circuits(options, proto)

        elif len(options['delete']) > 0:
            deletes = []
            for d in options['delete']:
                deletes.append(delete_circuit(proto, d, options['if-unused']))
            return defer.DeferredList(deletes)

        elif options['build']:
            return build_circuit(proto, options['build'].split(','))


cmd = CircCommand()
__all__ = ['cmd']
