import json
import platform
import os
import re
import time
import subprocess
import shutil
import tempfile
import functools
import pkg_resources
from six import BytesIO

try:
    import OpenSSL
except ImportError:
    raise RuntimeError("No OpenSSL: try 'pip install pyOpenSSL'")

import zope.interface
from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.internet import reactor, defer, ssl, endpoints, error
from twisted.internet._sslverify import PublicKey
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, ProxyAgent, RedirectAgent, ResponseDone, ResponseFailed
from twisted.web.iweb import IPolicyForHTTPS
from twisted.web.http_headers import Headers

from carml import util

DEBUG = False

# TODO:
#
# stream isolation: we should ask for a Tor connection, add a
# SOCKSPort to it for our own use, and connect to that (and then
# delete it from config when done). Unless there's an easier way.

# FIXME
# Twisted 14.0.0 can "just do" chain verification, I believe
# at *least* verify this does a similar thing, or just depend on >=14
# and delete it


@zope.interface.implementer(IPolicyForHTTPS)
class VerifyCertChainContextFactory(ssl.ClientContextFactory):
    def __init__(self, cert_chain):
        '''
        :param cert_chain:
            A list containing ``twisted.internet.ssl.Certificate``
            instances, with the "depth 0" one being first. Create
            these with ``twisted.internet.ssl.Certificate.loadPEM()``
        '''
        self.chain = {}         # key=int (depth), value=certificate
        for (i, cert) in enumerate(cert_chain):
            self.chain[i] = cert
        if DEBUG:
            for i in range(len(self.chain)):
                print('%d: %s' % (i, self.chain[i].getSubject()))

    def creatorForNetloc(self, hostname, port):
        # this should return a "creator" for the given hostname/port
        # -- we always return ourself because we only verify for a
        # single cert-chain so don't care what host we're visiting.
        return self

    def getContext(self):
        ctx = OpenSSL.SSL.Context(OpenSSL.SSL.TLSv1_METHOD)

        # load just the DigiCert root as "the" certificate store

        # WARNING although it's tempting to just call
        # set_default_verify_paths(), on OS X that fails. And
        # apparently if you fail to have a certificate store at all,
        # OpenSSL fails to actually-verify anything, even with all
        # the asking that follows here AND if you just "return 0"
        # from the verify_hostname callback...so don't do that.
        # FIXME there is something we could do here, maybe? can we
        # confirm that the cert store is in such a state that OpenSSL
        # will actually do verifications??!
        store = ctx.get_cert_store()
        store.add_cert(OpenSSL.crypto.load_certificate(OpenSSL.SSL.FILETYPE_PEM,
                                                       pkg_resources.resource_string('carml', 'keys/digicert-root-ca.pem')))

        # FAIL_IF_NO_PEER_CERT is requireCertification in Twisted
        # VERIFY_CLIENT_ONCE is verifyOnce in Twisted
        ctx.set_verify(OpenSSL.SSL.VERIFY_PEER | OpenSSL.SSL.VERIFY_FAIL_IF_NO_PEER_CERT | OpenSSL.SSL.VERIFY_CLIENT_ONCE,
                       self.verify_hostname)

        # verifyDepth from Twisted
        ctx.set_verify_depth(len(self.chain))

        # fixBrokenPeer from Twisted
        if False:
            _OP_ALL = getattr(OpenSSL.SSL, 'OP_ALL', 0x0000FFFF)
            ctx.set_options(_OP_ALL)

        # enableSingleUseKeys in Twisted
        ctx.set_options(OpenSSL.SSL.OP_SINGLE_DH_USE)

        # enableSessions in Twisted
        # see http://twistedmatrix.com/trac/browser/tags/releases/twisted-13.2.0/twisted/internet/_sslverify.py#L800
        # name = "%s-%d" % (reflect.qual(self.__class__), _sessionCounter())
        # sessionName = md5(networkString(name)).hexdigest()

        # _OP_NO_TICKET = 0x00004000
        # could disallow session tickets with ctx.set_options(self._OP_NO_TICKET)
        # if enableSessions in Twisted, calls ctx.set_session_id(md5(string + counter))
        return ctx

    def verify_hostname(self, connection, cert, errno, depth, preverifyOK):
        if DEBUG:
            print('Verify: pre=%d depth=%d cert=%s issuer=%s' % (preverifyOK,
                                                                 depth,
                                                                 cert.get_subject(),
                                                                 cert.get_issuer()))
        if not preverifyOK:
            # FIXME if below is true about constant-time, then this
            # shouldn't bail out early either...
            return False

        if depth >= len(self.chain):
            print("depth is %d, but we have a chain %d entries long." % (depth, len(self.chain)))
            return False

        # FIXME TODO requires thinking
        # need to ensure this is constant-time? e.g. compare hashes?
        # or are we already screwed on that since we'll bail out of
        # this whole "verify" callback stack early when one cert
        # fails?

        # correct way is to compare hashes (then we only have to store
        # the hash of the public cert, not the actual thing)

        verify_pubkey = PublicKey(cert.get_pubkey())
        golden_pubkey = self.chain[depth].getPublicKey()
        if DEBUG:
            print('incoming="%s", golden="%s"' % (verify_pubkey.keyHash(), golden_pubkey.keyHash()))

        if not golden_pubkey.matches(verify_pubkey):
            # getting out the CN (common name) for a nicer output,
            # but maybe we don't want that -- let "experts" examine
            # "failed.pem" and everyone else just needs to know "it
            # didn't work"?
            cn = ''
            for (k, v) in cert.get_subject().get_components():
                if k == 'CN':
                    cn = v
            common_name = ''.join(
                str(x[1])
                for x in cert.get_subject().get_components()
                if x[0] == 'CN'
            )
            print('Certificate chain verification failed for "%s".' % common_name)
            print('Public key md5 hash is "%s" but wanted "%s".' % (verify_pubkey.keyHash(), golden_pubkey.keyHash()))
            print('Dumping failing certificate to "failed.pem".')
            with open('failed.pem', 'a') as f:
                f.write(OpenSSL.crypto.dump_certificate(OpenSSL.SSL.FILETYPE_PEM, cert))
            return False

        # already checked preverifyOK
        return True


class ResponseReceiver(Protocol):
    def __init__(self, content, total, all_done):
        self.content = content
        self.total = int(total)
        self.current = 0
        self.last_output = None
        self.start = time.time()  # FIXME use IReactorTime to get this!
        self.all_done = all_done

    def dataReceived(self, data):
        self.content.write(data)
        self.update_progress(len(data))

    def update_progress(self, datalen):
        self.current += datalen
        if self.total > 1024 and self.current:
            howmuch = int((self.current * 100) / self.total)
            if self.last_output is None or howmuch - self.last_output >= 10:
                self.last_output = howmuch
                elapsed = time.time() - self.start
                velocity = self.current / elapsed
                cur = self.current
                tot = self.total
                for (order, unit) in [(1024, 'KiB'), (1024 * 1024, 'MiB'), (1024 * 1024 * 1024, 'GiB')]:
                    if tot / order < 100:
                        break
                cur /= order
                tot /= order
                units = unit
                estimate = self.total / velocity
                left = estimate - elapsed
                print('%s - %.1f of %.1f %s (%ds remaining)' % (util.pretty_progress(howmuch, 5), cur, tot, units, left))
                if self.current == self.total:
                    print('%0.2f MiB/s' % (self.total / (1024.0 * 1024) / elapsed))

    def connectionLost(self, reason):
        self.all_done.callback(str(reason))


async def download(agent, uri, filelike):
    resp = await agent.request(b'GET', uri)
    while resp.code == 302:
        newloc = resp.headers.getRawHeaders('location')[0]
        print("Following 302:", newloc)
        resp = await agent.request(b'GET', newloc.encode('ascii'))

    if resp.code != 200:
        raise RuntimeError('Failed to download "{}": {}'.format(uri, resp.code))
    done = defer.Deferred()
    total = resp.length
    dl = ResponseReceiver(filelike, total, done)
    resp.deliverBody(dl)
    await done


def get_download_urls(plat, arch, target_version):
    if '64' in arch:
        arch = 64
    else:
        arch = 32
    sig_fname = dict(linux='tor-browser-linux%d-%s_en-US.tar.xz.asc' % (arch, target_version),
                     darwin='TorBrowserBundle-%s-osx32_en-US.zip.asc' % (target_version, ),
                     windows='torbrowser-install-%s_en-US.exe.asc' % (target_version, ),
                     )[plat]

    dist_fname = sig_fname[:-4]
    return (sig_fname, dist_fname)


def extraction_instructions(fname):
    print("To extract:")
    print("   7z x %s" % fname)
    print("   tar xf %s" % fname[:-3])
    print("or just:")
    print('   7z -bd -so e "%s" | tar xf -' % fname)


def extract_7zip(fname):
    import backports.lzma as lzma
    import tarfile
    lz = lzma.open(str(fname))
    print('Extracting "%s"...' % fname)
    print('  decompressing...')
    tar = tarfile.open(fileobj=lz)

    def progress_generator(tar):
        prog = 0
        so_far = 0
        total = len(tar.getmembers())
        last = 0.0
        for ti in tar:
            so_far += 1
            percent = int((float(so_far) / float(total)) * 100.0)
            if last is None or percent - last >= (100.0 / 5.0):
                last = percent
                print('  %3d%% extracted' % percent)
            yield ti
    tar.extractall(members=progress_generator(tar))
    return None


async def run(reactor, cfg, tor, beta, alpha, use_clearnet, system_keychain, no_extract, no_launch):
    # NOTE the middle cert changed on April 10 or thereabouts;
    # still need to confirm this is legitimate?
    chain = [ssl.Certificate.loadPEM(pkg_resources.resource_string('carml', 'keys/torproject.pem')),
             ssl.Certificate.loadPEM(pkg_resources.resource_string('carml', 'keys/digicert-sha2.pem')),
             ssl.Certificate.loadPEM(pkg_resources.resource_string('carml', 'keys/digicert-root-ca.pem')),
             ]
    cf = VerifyCertChainContextFactory(chain)

    if use_clearnet:
        print(util.colors.red('WARNING') + ': downloading over plain Internet (not via Tor).')
        agent = Agent(reactor, contextFactory=cf)

    else:
        agent = tor.web_agent()

    # see onion.torproject.org to verify this is "www.torproject.org" equiv
    uri = b'http://expyuzz4wqqyqhjn.onion/projects/torbrowser/RecommendedTBBVersions'
    data = BytesIO()
    print(u'Getting recommended versions from "{}".'.format(uri.decode('ascii')))

    try:
        await download(agent, uri, data)
    except Exception as e:
        if hasattr(value, 'reasons'):
            msg = ''.join([str(r.value.args[-1]) for r in fail.value.reasons])
            raise RuntimeError(msg)
        raise

    # valid platforms from check.torproject.org can be one of:
    # 'Linux', 'MacOS' or 'Windows'
    plat = platform.system().lower()
    arch = platform.uname()[-2]
    plat_to_tor = dict(linux='Linux', darwin='MacOS', windows='Win')
    if plat not in plat_to_tor:
        print('Unknown platform "%s".' % plat)
        raise RuntimeError('Unknown platform "%s".' % plat)
    tor_plat = plat_to_tor[plat]

    data_bytes = data.getvalue()
    try:
        versions = json.loads(data_bytes.decode('utf8'))

    except:
        print('Error getting versions; invalid JSON:')
        print(data_bytes)
        raise RuntimeError('Invalid JSON:\n{}'.format(data_bytes))

    alpha_re = re.compile(r'[0-9]*.[0-9]*a[0-9]-(Windows|MacOS|Linux)')
    beta_re = re.compile(r'[0-9]*.[0-9]*b[0-9]-(Windows|MacOS|Linux)')
    hardened_re = re.compile(r'(.*)-hardened-(.*)')

    print(util.wrap(', '.join(versions), 60, '  '))
    alphas = [x for x in versions if alpha_re.match(x)]
    betas = [x for x in versions if beta_re.match(x)]
    hardened = [x for x in versions if  hardened_re.match(x)]
    others = set(versions).difference(alphas, betas, hardened)
    if alpha:
        versions = alphas
    elif beta:
        versions = betas
    else:
        versions = others

    if alphas and not alpha:
        print(util.colors.yellow("Note: there are alpha versions available; use --alpha to download."))
    if betas and not beta:
        print(util.colors.yellow("Note: there are beta versions available; use --beta to download."))
    if hardened:
        print(util.colors.yellow("Note: there are hardened versions available but we don't support downloading them yet."))

    target_version = None
    for v in versions:
        if v.endswith(tor_plat):
            target_version = v[:v.rfind('-')]

    if target_version is None:
        print("Can't find a version to download")
        print("          My platform is: %s (%s)" % (plat, plat_to_tor[plat]))
        print("  Potential versions are: %s" % ', '.join(versions))
        if beta:
            print("(Try without --beta)")
        elif alpha:
            print("(Try without --alpha)")
        raise RuntimeError("Nothing to download found.")

    # download the signature, then browser-bundle (if they don't
    # already exist locally).
    sig_fname, dist_fname = get_download_urls(plat, arch, target_version)
    for to_download in [sig_fname, dist_fname]:
        # this will 302 to the right spot, but goes to clearweb (dist.torproject.org) instead of onion service...
        # uri = u'http://expyuzz4wqqyqhjn.onion/dist/torbrowser/{}/{}'.format(target_version, to_download).encode('ascii')

        # see onion.torproject.org to verify this is "dist.torproject.org" equiv
        uri = u'http://rqef5a5mebgq46y5.onion/torbrowser/{}/{}'.format(target_version, to_download).encode('ascii')
        if os.path.exists(to_download):
            print(util.colors.red(to_download) + ': already exists, so not downloading.')
        else:
            try:
                with open(to_download, 'wb') as f:
                    print('Downloading "%s" from:\n   %s' % (to_download, uri.decode('ascii')))
                    await download(agent, uri, f)
            except Exception as e:
                print('removing "%s"...' % to_download)
                os.unlink(to_download)
                raise

    # ensure the signature matches
    if verify_signature(sig_fname, system_gpg=system_keychain):
        print(util.colors.green("Signature is good."))

        if no_extract:
            print("Download and signature check of the Tor Browser Bundle")
            print("has SUCCEEDED.\n")
            print("It is here: %s\n" % os.path.realpath(dist_fname))
            extraction_instructions(dist_fname)
            print("and then:")

        else:
            try:
                extract_7zip(dist_fname)
                print("Tor Browser Bundle downloaded and extracted.")

            except ImportError:
                msg = 'You need "backports.lzma" installed to do 7zip extraction.'
                print(util.colors.red('Error: ') + msg, isError=True)
                extraction_instructions(dist_fname)

        # running instructions
        lang = dist_fname[-12:-7]
        tbb_path = './tor-browser_%s/Browser/start-tor-browser' % lang
        if no_launch:
            print("To run: %s" % tbb_path)
        else:
            print("running: %s" % tbb_path)
            os.execl(tbb_path, tbb_path)

    else:
        print(util.colors.bold('Deleting tarball; signature verification failed.'))
        # XXX probably want an option to NOT do this ("for expert use" ...?)
        os.unlink(dist_fname)
        print('...however signature file is being kept for reference (%s).' % sig_fname)


def verify_signature(fname, system_gpg=False):

    verify_command = ['gpg', '--quiet']
    td = None
    status = False              # pessimism!

    try:
        if not system_gpg:
            # create temporary homedir
            td = tempfile.mkdtemp()
            verify_command.extend(['--homedir', td])

            # add Tor project-people keys to it (the ones who
            # sign releases, anyway)
            keys = []
            keys_path = os.path.join(td, 'keys')
            os.mkdir(keys_path)
            for k in pkg_resources.resource_listdir('carml', 'keys'):
                if k.endswith('.asc'):
                    keys.append(pkg_resources.resource_filename('carml', os.path.join('keys', k)))

            if len(keys) == 0:
                raise RuntimeError('Internal error: failed to find shipped keys.')

            try:
                if subprocess.check_call(['gpg', '--quiet', '--homedir', td, '--import'] + keys):
                    raise RuntimeError("Key import failed.")
            except IOError:
                raise RuntimeError("GPG verification failed; is GnuPG installed?")

        verify_command.extend(['--verify', fname])
        try:
            subprocess.check_call(verify_command)
            status = True

        except subprocess.CalledProcessError:
            print(util.colors.bold(util.colors.red("Signature verification failed.")))
            status = False

    finally:
        if td:
            shutil.rmtree(td)
    return status
