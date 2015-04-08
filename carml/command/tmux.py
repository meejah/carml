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


from carml.interface import ICarmlCommand
from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint


class TmuxOptions(usage.Options):
    """
    """

    optFlags = [
    ]

    optParameters = [
    ]


@implementer(ICarmlCommand, IPlugin)
class TmuxCommand(object):
    """
    Output for tmux's status-right. As in, put this in ~/.tmux.conf::

        set-option -g status-utf8 on
        set-option -g status-fg green
        set -g status-right '#(rainbarf --tmux --bright --no-battery --remaining)'
        set -g status-interval 2
    """

    name = 'tmux'
    help_text = """Show some informantion in your tmux status."""
    build_state = True
    load_routers = False
    controller_connection = True
    options_class = TmuxOptions

    def validate(self, options, mainoptions):
        "ICarmlCommand API"
        pass

    @defer.inlineCallbacks
    def run(self, options, mainoptions, state):
        "ICarmlCommand API"

        # because we asked not to load routers (for speed) we do have
        # to "update" the one's we'll be interested in.
        if False:
            routers = set()
            for circ in state.circuits.values():
                for r in circ.path:
                    routers.add(r.id_hex)
            yield state.update_routers(routers)

        for circ in state.circuits.values():
            if len(circ.streams) == 0:
                continue

            for r in circ.path:
                if r.location.countrycode is None:
                    yield r.get_country()
            # print(circ)
            path = u'>'.join(map(lambda r: r.location.countrycode or '__', circ.path))
            #print(u"#[fg=colour46,bg=colour28]{}#[fg=colour28,bg=colour22]{}".format(path, len(circ.streams)), end='')
            print(u"#[fg=colour28,bg=colour22]{}#[fg=colour46,bg=colour28]{}".format(path, len(circ.streams)), end='')

        total = len(state.circuits)
        general = len(filter(lambda c: c.purpose == 'GENERAL', state.circuits.values()))
        part = int(general / float(total) * 7)
        msg = u'#[fg=colour32,bg=colour17]%s' % unichr(0x2581 + part)
        print(msg.encode('utf8'), end='')

        onions = len(filter(lambda c: c.purpose.startswith('HS_'), state.circuits.values()))
        # print("XXX", general, onions)
        part = int(onions / float(total) * 7)
        msg = u'#[fg=colour160,bg=colour17]%s' % unichr(0x2581 + part)
        print(msg.encode('utf8'))
        # util.dump_circuits(state, True)
        # stuff like: #[fg=colour46,bg=colour28]

# the IPlugin/getPlugin stuff from Twisted picks up any object from
# here than implements ICarmlCommand -- so we need to instantiate one
cmd = TmuxCommand()
