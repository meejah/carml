# This is intended to be copy-pasted, and search-replace "blam" with
# your command-name as a starting-point for a new command. To use:
#
# 1. copy/paste to `cmdname.py` in a directory and with PYTHONPATH
#    such that it's in a carml/command sub-directory. E.g. adding
#    `example_extension` from the source code to PYTHONPATH will make the
#    `blam` command avaliable:
#
#        virtualenv venv
#        . ./venv/bin/acvtivate
#        python setup.py develop
#        carml blam --amaze 5
#
# 2. delete the example optFlags and optParameters entries and add any
#    of your own.
#
#        http://twistedmatrix.com/documents/current/core/howto/options.html
#
# 3. change `name` and `help_text` members of the command object
#
# 4. Decide if you need no Tor connection (e.g. you're going to launch
#    your own, like "pastebin" command), or if you need a TorState
#    object instead (e.g. you want to use the high-level circuit or
#    stream or event interface) and if so, whether to load all the
#    routers (relays) or not. Then set build_state, load_routers and
#    controller_connection as appropriate.
#
# 5. gut validate() method and do any options-validation you need
#    to. Note you have no Tor connection at this point; if you require
#    one to do validation, you have to error out of run() instead.
#
# 6. implement run() method. This may return:
#
#    a. A Deferred instance, in which case carml command-line exits
#       when the Deferred callback()s or errback()s.
#    b. None, in which case the command itself must call
#       reactor.stop() exactly once in order to exit
#
#    In either case, you can easily make a command that never
#    exits. (It will clean up if user does control-c or sends TERM
#    etc.)

import zope.interface
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.internet import reactor
from twisted.internet import defer

from carml.interface import ICarmlCommand

class BlamOptions(usage.Options):
    """
    See the Twisted docs for option arguments, but some common
    examples are below.
    """

    optFlags = [
        ('booooring', 'b', 'If specified, be boring.'),
        ]

    optParameters = [
        ('amaze', 'a', 0, 'Specify an amazement level. 0-10', int)
        ]


@zope.interface.implementer(ICarmlCommand)
@zope.interface.implementer(IPlugin)
class BlamCommand(object):
    """
    The actual command, which implements ICarmlCommand and Twisted's
    IPlugin.
    
    note to self (FIXME): can I just have ICarmlCommand derive from
    IPlugin?
    """

    # these are all Attributes of the ICarmlCommand interface
    name = 'blam'
    help_text = """A template command."""
    build_state = False
    load_routers = False
    controller_connection = True
    options_class = BlamOptions

    def validate(self, options, mainoptions):
        "ICarmlCommand API"

        if options['booooring'] and options['amaze']:
            raise RuntimeError("Can't specify both boredom *and* amazement.")
        if options['amaze'] < 0 or options['amaze'] >= 10:
            raise RuntimeError("Only amazing from 0-10...")
        return

    def run(self, options, mainoptions, connection):
        "ICarmlCommand API"

        if not options['booooring']:
            print "Blam!"
            if options['amaze']:
                for x in xrange(options['amaze']):
                    print ' ' + ('-' * x * 2) + '-> Such amaze!'
        return defer.succeed(self)

## the IPlugin/getPlugin stuff from Twisted picks up any object from
## this file than implements ICarmlCommand -- so we need to
## instantiate one
cmd = BlamCommand()
