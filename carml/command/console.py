import os
import functools
import curses

import zope.interface
from twisted.python import usage
from twisted.internet import defer, reactor

import txtorcon

from interface import ICarmlCommand
import subcommands

class ConsoleOptions(usage.Options):
    def __init__(self):
        super(ConsoleOptions, self).__init__()
        self.longOpt.remove('version')
        self.longOpt.remove('help')

    def getUsage(self, **kw):
        return "Options:\n   Pass any number of strings as args, which will be passed to GETINFO and printed out."

class Screen:
    """
    Fake filedescriptor to be registered as a reader with the twisted
    reactor.
    """

    zope.interface.implements(txtorcon.ICircuitListener, 
                              txtorcon.IStreamListener)
    
    def fileno(self):
        """ We want to select on FD 0 """
        return 0
        
    def logPrefix(self):
        return 'curses'

    def __init__(self, stdscr):
        self.stdscr = stdscr

        self.current_input = ''
        """what the user has typed so far"""

        self.lines = []
        """accumulated output"""

        # set screen attributes
        self.stdscr.nodelay(1) # this is used to make input calls non-blocking
        curses.cbreak()
        self.stdscr.keypad(1)
        curses.curs_set(0)     # no annoying mouse cursor

        self.rows, self.cols = self.stdscr.getmaxyx()

        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)

        self.lines.append('Welcome to the carml console.')
        self.lines.append('Type "help" or "?" plus optional command for assistance.')

        self.paintStatus('not connected')
        self.torstate = None

    def set_torstate(self, torstate):
        self.torstate = torstate
        self.draw()
        self.torstate.add_circuit_listener(self)
        self.torstate.add_stream_listener(self)

    def _generic_listener(self, *args, **kw):
        self.draw()

    circuit_new = _generic_listener
    circuit_launched = _generic_listener
    circuit_extend = _generic_listener
    circuit_built = _generic_listener
    circuit_closed = _generic_listener
    circuit_failed = _generic_listener
    stream_new = _generic_listener
    stream_succeeded = _generic_listener
    stream_attach = _generic_listener
    stream_detach = _generic_listener
    stream_closed = _generic_listener
    stream_failed = _generic_listener

    def connectionLost(self, reason):
        log.msg("connectionLost %s\n", reason)
        self.close()

    def draw(self):
        self.stdscr.clear()
        if self.torstate is None:
            self.paintStatus('not connected')
            self.stdscr.refresh()
            return

        self.paintStatus('%d routers, %d guards, %d circuits, %d streams' % (len(self.torstate.routers_by_name), len(self.torstate.guards), len(self.torstate.circuits), len(self.torstate.streams)))

        inset = []
        for circ in self.torstate.circuits.values():
            line = '%d: %s %s' % (circ.id, circ.state[0], 
                                  '->'.join([r.name for r in circ.path]))
            inset.append(line)
            for stream in circ.streams:
                line = '  -> %s:%d' % (stream.target_host, stream.target_port)
                inset.append(line)
        if len(inset) == 0:
            inset.append('(No circuits)')
        max_length = max(map(len, inset))
        x = self.cols - max_length - 1
        for y in xrange(len(inset)):
            self.stdscr.addstr(y, x, inset[y],
                               curses.color_pair(3))
            
            
        i = 0
        index = len(self.lines) - 1
## -3 so we're above the status line, and the other line
        while i < (self.rows - 3) and index >= 0:
            self.stdscr.addstr(self.rows - 3 - i, 0,
                               self.lines[index],
                               curses.color_pair(2))
            i = i + 1
            index = index - 1

        self.stdscr.addstr(self.rows-1, 0,
                           self.current_input + (' ' * (
                           self.cols-len(self.current_input)-2)))
        self.stdscr.refresh()

    def paintStatus(self, text):
        if len(text) > self.cols: raise TextTooLongError
        self.stdscr.addstr(self.rows-2,0,text + ' ' * (self.cols-len(text)),
                           curses.color_pair(1))
        # move cursor to input line
        self.stdscr.move(self.rows-1, self.cols-1)

    def processCommand(self, cmd):
        if cmd == 'quit':
            reactor.stop()

    def doTabCompletion(self):
        pass

    def doRead(self):
        """ Input is ready! """
        curses.noecho()
        c = self.stdscr.getch() # read a character
        self.draw()
        return

        if False:##c == ord('q'):
            # scorch the earth; FIXME
            reactor.stop()
            
        elif c == curses.KEY_BACKSPACE:
            self.current_input = self.current_input[:-1]

        elif c == curses.KEY_ENTER or c == 10:
            self.addLine(self.current_input)
            # for testing too
            self.processCommand(self.current_input)
            self.stdscr.refresh()
            self.current_input = ''

        elif c == curses.KEY_TAB:
            self.doTabCompletion()

        else:
            if len(self.current_input) == self.cols-2: return
            self.current_input = self.current_input + chr(c)

        self.draw()

    def close(self):
        """ clean up """

        curses.nocbreak()
        self.stdscr.keypad(0)
        curses.echo()
        curses.endwin()
        reactor.stop()
        log.msg("close() called")


class ConsoleSubCommand(object):
    zope.interface.implements(ICarmlCommand)

    ## Attributes specified by ICarmlCommand
    options_class = ConsoleOptions
    help_text = 'Start an interactive console to run commands in.'
    build_state = True

    def validate(self, options, mainoptions):
        pass

    def run(self, options, state):
        """
        ICarmlCommand API
        """

        stdscr = curses.initscr()
        screen = Screen(stdscr)
        screen.set_torstate(state)
        ## FIXME no global reactor
        reactor.addReader(screen)
        stdscr.refresh()


subcommands.register('console', ConsoleSubCommand())
