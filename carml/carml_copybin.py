from __future__ import print_function
import sys
import time
import functools

from zope.interface import implementer
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.web.iweb import IAgentEndpointFactory
from twisted.web.client import Agent, readBody
from twisted.internet import reactor
from twisted.internet.protocol import Protocol


from carml import util
import txtorcon
from txtorcon import TCPHiddenServiceEndpoint


@defer.inlineCallbacks
def run(reactor, cfg, tor, service):
    config = yield tor.get_config()
    socks = yield tor.protocol.get_info('net/listeners/socks')
    socks = socks['net/listeners/socks']
    socks_host, socks_port = socks.split(':')

    args = service.split(':')
    onion = args[1]
    cookie = args[2].split('=')[1]

    auth = '%s %s' % (onion, cookie)
    if auth not in config.HidServAuth:
        config.HidServAuth.append(auth)
    yield config.save()

    agent = tor.web_agent()
    res = yield agent.request('GET', 'http://{}/'.format(onion))
    print('Response: "{} {}" with {} bytes'.format(res.code, res.phrase, res.length))
    data = yield readBody(res)
    print(data)
