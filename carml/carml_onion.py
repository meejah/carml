import sys
import time
import json
import functools

import zope.interface
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import serverFromString
from twisted.web.http import HTTPChannel
from twisted.web.static import Data
from twisted.web.resource import Resource
from twisted.web.server import Site

from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint


async def run(reactor, cfg, tor, ports, version, private_key, show_private_key, detach):

    def fix_port(p):
        """
        if the user only specified one port, we should forward to the same
        local one (otherwise txtorcon will pick one for us)
        """
        if isinstance(p, tuple):
            return p
        return p, p
    ports = [fix_port(port) for port in ports]

    if not cfg.json:
        if private_key:
            print("Re-creating v{} onion-service with given private key...".format(version))
        else:
            print("Creating v{} onion-service...".format(version))

    def update(pct, tag, description):
        if not cfg.json:
            print("  {}: {}".format(util.pretty_progress(pct), description))
    hs = await tor.create_onion_service(
        ports,
        version=version,
        progress=update,
        await_all_uploads=True,
        private_key=private_key,
        detach=detach,
    )
    if not cfg.json:
        print("published to all HSDirs")

    async def remove():
        if not cfg.json:
            print("removing onion-service")
        await hs.remove()
    reactor.addSystemEventTrigger('before', 'shutdown', remove)

    if not cfg.json:
        print("Running an Onion Service mapping the following ports:")

    js = {
        "hostname": hs.hostname,
        "ports": [],
    }

    for port in ports:
        if isinstance(port, tuple):
            remote_port, local_port = port
        else:
            remote_port, local_port = port, port

        if cfg.json:
            js['ports'].append({
                "remote": remote_port,
                "local": local_port,
            })
        if not cfg.json:
            print(
                "{}:{} (remote) -> {} (local)".format(
                    hs.hostname,
                    remote_port,
                    local_port,
                )
            )

    if show_private_key:
        if cfg.json:
            js["private_key"] = hs.private_key
        else:
            print(
                "To re-launch this service, specify:\n"
                "  --private-key {}".format(
                    hs.private_key,
                )
            )

    if cfg.json:
        print(json.dumps(js, indent=4))

    if not detach:
        # we never callback() on this, so we serve forever
        await Deferred()
