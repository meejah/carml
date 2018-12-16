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


async def run(reactor, cfg, tor, service):
    config = await tor.get_config()
    socks = await tor.protocol.get_info('net/listeners/socks')
    socks = socks['net/listeners/socks']
    socks_host, socks_port = socks.split(':')

    args = service.split(':')
    onion = args[1]
    cookie = args[2].split('=')[1]

    auth = '%s %s' % (onion, cookie)
    if auth not in config.HidServAuth:
        config.HidServAuth.append(auth)
    await config.save()

    agent = tor.web_agent()
    url = 'http://{}'.format(onion).encode('ascii')
    print("retrieving: {}".format(url))
    res = await agent.request(b'GET', url)
    print('Response: "{} {}" with {} bytes'.format(res.code, res.phrase, res.length))
    data = await readBody(res)
    print(data.decode('utf8'))
