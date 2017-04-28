from __future__ import absolute_import

import sys

from twisted.internet import defer, task
from twisted.internet.endpoints import clientFromString
from twisted.python.failure import Failure

import click
import txtorcon

from . import carml_check_pypi


class Config(object):
    '''
    Passed as the Click object (@pass_obj) to all CLI methods.
    '''


@click.group()
@click.option('--timestamps', '-t', help='Prepend timestamps to each line.', is_flag=True)
@click.option('--no-color', '-n', help='Same as --color=no.', is_flag=True, default=None)
@click.option('--info', '-i', help='Show version of Tor we connect to (on stderr).', is_flag=True)
@click.option('--quiet', '-q', help='Some commands show less information with this option.', is_flag=True)
@click.option('--debug', '-d', help='Debug; print stack traces on error.', is_flag=True)
@click.option(
    '--password', '-p',
    help=('Password to authenticate to Tor with. Using cookie-based authentication'
          'is much easier if you are on the same machine.'),
    default=None,
    required=False,
)
@click.option(
    '--connect', '-c',
    default='tcp:host=127.0.0.1:port=9051',
    help=('Where to connect to Tor. This accepts any Twisted client endpoint '
          'string, or an ip:port pair. Examples: "tcp:localhost:9151" or '
          '"unix:/var/run/tor/control".'),
    metavar='ENDPOINT',
)
@click.option(
    '--color', '-C',
    type=click.Choice(['auto', 'no', 'always']),
    default='auto',
    help='Colourize output using ANSI commands.',
)
@click.pass_context
def carml(ctx, timestamps, no_color, info, quiet, debug, password, connect, color):
    if (color == 'always' and no_color) or \
       (color == 'no' and no_color is True):
        raise click.UsageError(
            "--no-color={} but --color={}".format(no_color, color)
        )

    cfg = Config()
    ctx.obj = cfg

    cfg.timestamps = timestamps
    cfg.no_color = no_color
    cfg.info = info
    cfg.quiet = quiet
    cfg.debug = debug
    cfg.password = password
    cfg.connect = connect
    cfg.color = color


def _run_command(cmd, cfg, *args, **kwargs):

    @defer.inlineCallbacks
    def _startup(reactor):
        ep = clientFromString(reactor, cfg.connect)
        tor = yield txtorcon.connect(reactor, ep)

        if cfg.info:
            info = yield tor.proto.get_info('version', 'status/version/current', 'dormant')
            click.echo(
                'Connected to a Tor version "{version}" (status: '
                '{status/version/current}).\n'.format(**info)
            )
        yield defer.maybeDeferred(
            cmd, reactor, cfg, tor, *args, **kwargs
        )

    from twisted.internet import reactor
    codes = [0]

    def _the_bad_stuff(f):
        print("Error: {}".format(f.value))
        if cfg.debug:
            print(f.getTraceback())
        codes[0] = 1
        return None

    def _go():
        d = _startup(reactor)
        d.addErrback(_the_bad_stuff)
        d.addBoth(lambda _: reactor.stop())

    reactor.callWhenRunning(_go)
    reactor.run()
    sys.exit(codes[0])


@carml.command()
@click.option(
    '--package', '-p',
    help='Name of the package to check (unfortunately, case matters)',
    required=True,
)
@click.option(
    '--revision', '-r',
    help='Specific version to check (default: latest)',
    default=None,
)
@click.pass_obj
def check_pypi(cfg, package, revision):
    """
    Check a PyPI package hash across multiple circuits.
    """
    return _run_command(
        carml_check_pypi.run,
        cfg, package, revision,
    )
