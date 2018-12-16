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


async def run(reactor, cfg, tor):
    state = await tor.create_state()

    for circ in state.circuits.values():
        if len(circ.streams) == 0:
            continue

        for r in circ.path:
            if r.location.countrycode is None:
                await r.get_country()
        path = u'>'.join(r.location.countrycode or '__' for r in circ.path)
        print(u"#[fg=colour28,bg=colour22]{}#[fg=colour46,bg=colour28]{}".format(path, len(circ.streams)), end='')

    total = len(state.circuits)
    general = len([c for c in state.circuits.values() if c.purpose == 'GENERAL'])
    part = int(general / float(total) * 7)
    msg = u'#[fg=colour32,bg=colour17]%s' % chr(0x2581 + part)
    print(msg.encode('utf8'), end='')

    onions = len([c for c in state.circuits.values() if c.purpose.startswith('HS_')])
    part = int(onions / float(total) * 7)
    msg = u'#[fg=colour160,bg=colour17]%s' % chr(0x2581 + part)
    print(msg.encode('utf8'))
