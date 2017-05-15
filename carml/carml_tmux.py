from __future__ import print_function
import sys
import time
import functools

from zope.interface import implementer
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import Protocol


from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint


@defer.inlineCallbacks
def run(reactor, cfg, tor):
    state = yield tor.create_state()

    for circ in state.circuits.values():
        if len(circ.streams) == 0:
            continue

        for r in circ.path:
            if r.location.countrycode is None:
                yield r.get_country()
        path = u'>'.join(map(lambda r: r.location.countrycode or '__', circ.path))
        print(u"#[fg=colour28,bg=colour22]{}#[fg=colour46,bg=colour28]{}".format(path, len(circ.streams)), end='')

    total = len(state.circuits)
    general = len(filter(lambda c: c.purpose == 'GENERAL', state.circuits.values()))
    part = int(general / float(total) * 7)
    msg = u'#[fg=colour32,bg=colour17]%s' % unichr(0x2581 + part)
    print(msg.encode('utf8'), end='')

    onions = len(filter(lambda c: c.purpose.startswith('HS_'), state.circuits.values()))
    part = int(onions / float(total) * 7)
    msg = u'#[fg=colour160,bg=colour17]%s' % unichr(0x2581 + part)
    print(msg.encode('utf8'))
