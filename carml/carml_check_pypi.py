# check Python Package Index (PyPI) over 3 different circuits and
# compare sha256 hashes. suitable for use in requirements.txt with
# "twine"
from __future__ import print_function

from zope.interface import implementer
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet import endpoints
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.web.client import readBody

import json
import hashlib
from base64 import urlsafe_b64encode
from distutils.version import LooseVersion

import txtorcon
import txtorcon.socks


@inlineCallbacks
def run(reactor, cfg, tor, package_name, package_version):
    agent = tor.web_agent()
    state = yield tor.create_state()

    # download metadata from PyPI over "any" circuit
    uri = b'https://pypi.python.org/pypi/{}/json'.format(package_name)
    print("downloading: '{}'".format(uri))
    resp = yield agent.request(b'GET', uri)
    data = yield readBody(resp)
    data = json.loads(data)

    # did we get a valid sdist URL somewhere?
    sdist_url = None
    version = None
    if package_version is None:
        # print data['releases'].keys()
        available = [LooseVersion(x) for x in data['releases'].keys()]
        package_version = str(sorted(available)[-1])
        print("Using version: {}".format(package_version))

    for url in data['releases'][package_version]:
        if url['packagetype'] == 'sdist':
            sdist_url = url['url'].encode('UTF8')
            version = url['filename']
    if sdist_url is None:
        print("Error: couldn't find any 'sdist' URLs")
        raise RuntimeError("No sdist URL")
    else:
        print("Found sdist: {} for {}".format(sdist_url, version))

    # download the distribution over several different circuits,
    # and record the sha256 hash each time.
    digests = []
    while len(digests) < 3:
        circ = yield state.build_circuit()
        try:
            yield circ.when_built()
        except Exception:
            print("Circuit failed; trying another.")
            continue

        print(
            "Built circuit: {}".format(
                ' -> '.join([r.ip for r in circ.path]),
            )
        )

        try:
            agent = circ.web_agent(reactor, tor._default_socks_endpoint())
            resp = yield agent.request(b'GET', sdist_url)
            # FIXME could stream this to the hasher with a custom
            # protocol, but teh RAMz they are cheap
            tarball = yield readBody(resp)
        except txtorcon.socks.TtlExpiredError as e:
            print("Timed out: {}".format(e))
            continue
        except Exception as e:
            print("Something went wrong: {}".format(e))
            continue

        hasher = hashlib.new('sha256')
        hasher.update(tarball)
        # the whole point is to match peep's hashes, and this is
        # exactly what it does:
        digest = urlsafe_b64encode(hasher.digest()).decode('ascii').rstrip('=')
        digests.append((sdist_url, circ, digest))
        print("sha256:", digest)

    print("Found hashes:")
    feel_fear = False
    for (url, circ, digest) in digests:
        print(digest)
        if digest != digests[0][-1]:
            print("Fearsome Warning! Mismatched digest!!")
            feel_fear = True
            print("Circuit:", '->'.join(map(lambda r: r.hex_id, circ.path)))

    if feel_fear:
        print("****\n  Something fishy!\n****")
    else:
        print("Add this to requirements.txt for peep:")
        print()
        print("# sha256: {}".format(digests[0][-1]))
        print("{}=={}".format(package_name, package_version))
    return
