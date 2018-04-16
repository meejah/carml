import os
import sys
import time
import shutil
import tempfile
import functools
import subprocess

import zope.interface
from twisted.python import usage, log
from twisted.protocols.basic import LineReceiver
from twisted.internet import defer, reactor, stdio

import txtorcon
from carml import util

_log = functools.partial(log.msg, system='carml')


def dump_xplanet_files(cfg, all, arc_file, file, follow, state):
    print("dumping", arc_file, file)
    unique_routers = set()
    routers_in_streams = set()
    if all:
        map(unique_routers.add, state.routers.values())

    else:
        # this method does only active routers (i.e. in at least
        # one of your streams) and colours guards as green
        for circ in state.circuits.values():
            map(unique_routers.add, circ.path)
        map(unique_routers.add, state.entry_guards.values())

        # cache any router that's used by any current circuit right now
        for circ in state.circuits.values():
            map(routers_in_streams.add, circ.path)

        if False:
            map(unique_routers.add, state.guards.values())

    header = '## Auto-generated "{}" by carml'.format(time.asctime())
    if arc_file is not None:
        arc_file.write(header + '\n')
        arc_file.write('## format: lat0 lng0 lat1 lng1\n\n')

        def gen_colors(r, g, b):
            while True:
                yield '0x%02x%02x%02x' % (r, g, b)
                r = int(r * 0.65)
                g = int(g * 0.65)
                b = int(b * 0.65)

        def gen_start_colors():
            while True:
                yield 0xb5, 0x89, 0x00
                yield 0xcb, 0x4b, 0x16
                yield 0xdc, 0x32, 0x2f
                yield 0xd3, 0x36, 0x82
                yield 0x6c, 0x71, 0xc4
                yield 0x26, 0x8b, 0xd2
                yield 0x2a, 0xa1, 0x98
                yield 0x85, 0x99, 0x00

        start_color = gen_start_colors()
        for circ in state.circuits.values():
            arc_file.write('## circuit {}\n'.format(circ.id))
            arc_colors = gen_colors(*start_color.next())
            for (i, link) in enumerate(circ.path[:-1]):
                nxt = circ.path[i + 1]
                if link.location.latlng[0] and nxt.location.latlng[0]:
                    arc_file.write('{} {} '.format(*link.location.latlng))
                    arc_file.write('{} {} '.format(*nxt.location.latlng))
                    arc_file.write('color={} thickness=2 # {}->{}\n'.format(arc_colors.next(), link.id_hex, nxt.id_hex))

    markerfile = file
    markerfile.write(header + '\n')
    markerfile.write('## {} unique routers\n'.format(len(unique_routers)))
    markerfile.write('## format: lat lng "name-or-hash" # hex-id\n\n')

    misses = 0
    for router in unique_routers:
        lat, lng = router.location.latlng
        if lat is not None and lng is not None:
            color = 'purple'
            if router.id_hex in state.entry_guards:
                color = 'red'
            if router in routers_in_streams:
                color = 'green'
            if color != 'green':
                markerfile.write('%02.5f %02.5f color=%s # %s\n' % (lat, lng, color, router.id_hex))

        else:
            markerfile.write('# unknown location: %s (%s)\n' % (router.unique_name, router.id_hex))
            misses += 1

    for router in routers_in_streams:
        lat, lng = router.location.latlng
        if lat and lng:
            markerfile.write('%02.5f %02.5f color=green # %s %s\n' % (lat, lng, router.unique_name, router.id_hex))

    if False:
        for stream in state.streams.values():
            for (idx, router) in enumerate(stream.circuit.path):
                lat, lng = router.location.latlng
                if lat and lng:
                    markerfile.write('%02.5f %02.5f "%d:%s" color=green # %s\n' % (lat, lng, idx, router.unique_name, router.id_hex))

    if not cfg.quiet:
        if misses == len(unique_routers):
            print('NOTE: it seems NO routers had location information.')
            print("Things to try:")
            print(" * install MaxMind IP geolocation database.")
            print(" * pip install geoip")
        else:
            if misses == 0:
                print('All routers had location information.')
            else:
                print('%d (%2.0f%%) routers with no geoip information.' % (misses, (float(misses) / len(unique_routers)) * 100.0))


class CircuitListener(txtorcon.CircuitListenerMixin):
    next_defer = None

    def _trigger_event(self, circuit, **kw):
        print(circuit)
        if self.next_defer:
            nd = self.next_defer
            self.next_defer = None
            nd.callback(circuit)

    circuit_failed = _trigger_event
    circuit_closed = _trigger_event
    circuit_built = _trigger_event


def generate_circuit_builds(listener):
    def generator():
        while True:
            listener.next_defer = defer.Deferred()
            yield listener.next_defer
    return generator()


@defer.inlineCallbacks
def continuously_update_xplanet(cfg, all, arc_file, file, follow, state):
    listener = CircuitListener()
    gen = generate_circuit_builds(listener)
    state.add_circuit_listener(listener)

    tmpdir = tempfile.mkdtemp()
    reactor.addSystemEventTrigger('before', 'shutdown',
                                  functools.partial(shutil.rmtree, tmpdir))

    marker_fname = os.path.join(tmpdir, 'xplanet_markers')
    arcs_fname = os.path.join(tmpdir, 'xplanet_arcs')
    cfg_fname = os.path.join(tmpdir, 'xplanet-config')

    with open(cfg_fname, 'w') as f:
        f.write('''[earth]\n"Earth"\nmarker_file=%s\narc_file=%s\n''' % (marker_fname, arcs_fname))

    cmd = ['xplanet',
           '-num_times', '1',
           '-projection', 'rectangular',
           '-config', cfg_fname,
           ]
    os.chdir(tmpdir)
    while True:
        file = open(marker_fname, 'w')
        arc_file = open(arcs_fname, 'w')
        dump_xplanet_files(cfg, all, arc_file, file, follow, state)
        if not cfg.quiet:
            print(' '.join(cmd), subprocess.check_output(cmd))

        if not follow:
            return

        circ = yield gen.next()
        print(circ)


@defer.inlineCallbacks
def run(reactor, cfg, tor, all, execute, follow, arc_file, file):

    state = yield tor.create_state()
    if follow or execute:
        yield continuously_update_xplanet(cfg, all, arc_file, file, follow, state)
    else:
        dump_xplanet_files(cfg, all, arc_file, file, follow, state)
