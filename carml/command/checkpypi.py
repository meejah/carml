# check Python Package Index (PyPI) over 3 different circuits and
# compare sha256 hashes. suitable for use in requirements.txt with
# "twine"

from zope.interface import implementer
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet import endpoints
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.web.client import readBody

from carml.interface import ICarmlCommand

import json
import hashlib
from base64 import urlsafe_b64encode
from distutils.version import LooseVersion

import txtorcon
import txsocksx
import txsocksx.http
import txsocksx.errors


class CheckPyPIOptions(usage.Options):
    """
    See the Twisted docs for option arguments, but some common
    examples are below.
    """

    optFlags = [
    ]

    optParameters = [
        ('package', 'p', None, 'Name of the package to check (unfortunately, case matters)', str),
        ('revision', 'r', None, 'Specific version to check (default: latest)', str),
    ]


@implementer(ICarmlCommand)
@implementer(IPlugin)
class CheckPyPICommand(object):
    """
    The actual command, which implements ICarmlCommand and Twisted's
    IPlugin.

    note to self (FIXME): can I just have ICarmlCommand derive from
    IPlugin?
    """

    # these are all Attributes of the ICarmlCommand interface
    name = 'checkpypi'
    help_text = """Check a PyPI package hash across multiple circuits."""
    build_state = True
    load_routers = True
    controller_connection = True
    options_class = CheckPyPIOptions

    def validate(self, options, mainoptions):
        """ICarmlCommand API"""
        if not options['package']:
            raise RuntimeError("Must supply --package")
        return None

    @inlineCallbacks
    def run(self, options, mainoptions, state):
        """ICarmlCommand API"""

        package_name = options['package']
        package_version = options['revision']

        @implementer(txtorcon.IStreamAttacher)
        class MyAttacher(object):
            circ = None
            def attach_stream(self, stream, circuits):
                print "Via:", ' '.join(map(lambda r: r.id_hex, self.circ.path))
                return self.circ

        # ask Tor what port it's running on
        port = yield state.protocol.get_info('net/listeners/socks')
        socks = 'tcp:' + port['net/listeners/socks']
        tor_ep = endpoints.clientFromString(reactor, socks)
        agent = txsocksx.http.SOCKS5Agent(reactor, proxyEndpoint=tor_ep)

        # download metadata from PyPI over "any" circuit
        uri = 'https://pypi.python.org/pypi/%s/json' % package_name
        print "downloading:", uri
        resp = yield agent.request('GET', uri)
        data = yield readBody(resp)
        data = json.loads(data)

        # did we get a valid sdist URL somewhere?
        sdist_url = None
        version = None
        if package_version is None:
            # print data['releases'].keys()
            available = [LooseVersion(x) for x in data['releases'].keys()]
            package_version = str(sorted(available)[-1])
            print "Using version:", package_version

        for url in data['releases'][package_version]:
            if url['packagetype'] == 'sdist':
                sdist_url = url['url'].encode('UTF8')
                version = url['filename']
        if sdist_url is None:
            print "Error: couldn't find any 'sdist' URLs"
            raise RuntimeError("No sdist URL")
        else:
            print "Found sdist:", sdist_url, "for", version

        # create our custom attacher
        attach = MyAttacher()
        yield state.set_attacher(attach, reactor)

        # download the distribution over several different circuits,
        # and record the sha256 hash each time.
        digests = []
        while len(digests) < 3:
            circ = yield state.build_circuit()
            try:
                yield circ.when_built()
            except Exception:
                print "Circuit failed; trying another."
                continue
            attach.circ = circ
            print "Built circuit"

            try:
                resp = yield agent.request('GET', sdist_url)
                # FIXME could stream this to the hasher with a custom
                # protocol, but teh RAMz they are cheap
                tarball = yield readBody(resp)
            except txsocksx.errors.TTLExpired as e:
                print "Timed out: {}".format(e)
                continue
            except Exception as e:
                print "Something went wrong: {}".format(e)
                continue

            hasher = hashlib.new('sha256')
            hasher.update(tarball)
            # the whole point is to match peep's hashes, and this is
            # exactly what it does:
            digest = urlsafe_b64encode(hasher.digest()).decode('ascii').rstrip('=')
            digests.append((sdist_url, circ, digest))
            print "sha256:", digest

        print "Found hashes:"
        feel_fear = False
        for (url, circ, digest) in digests:
            print digest
            if digest != digests[0][-1]:
                print "Fearsome Warning! Mismatched digest!!"
                feel_fear = True
                print "Circuit:", '->'.join(map(lambda r: r.hex_id, circ.path))

        if feel_fear:
            print "****\n  Something fishy!\n****"
        else:
            print "Add this to requirements.txt for peep:"
            print
            print "# sha256: {}".format(digests[0][-1])
            print "{}=={}".format(package_name, package_version)
        return

cmd = CheckPyPICommand()
