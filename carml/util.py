'''
Utility functions.

Probably some of these could be replaced by a library or two,
especially the progress-bar hackery. The colour stuff is also a little
wonky.
'''

from __future__ import print_function

import datetime
import functools

import colors


class NoColor(object):
    '''
    Replaces color methods with no-ops if we decide to turn off
    colored output.
    '''

    def __init__(self):
        self._overrides = [x for x in dir(colors) if not x.startswith('__')]

    def __getattr__(self, name):
        '''
        All the "things" in the colors library are methods; so, if we
        didn't ask for a magic-python method, we return the "noop"
        function which doesn't do anything to your string. The colors
        library would add ANSI commands around it.
        '''
        if name in self._overrides:
            return lambda x: x
        return self.__dict__[name]


def turn_off_color():
    "Here be the wonky bits..."
    global colors
    colors = NoColor()

def pretty_progress(percent, size=10, ascii=False):
    """
    Displays a unicode or ascii based progress bar of a certain
    length. Should we just depend on a library instead?
    """

    curr = int(percent / 100.0 * size)
    part = (percent / (100.0 / size)) - curr

    if ascii:
        part = int(part * 4)
        part = '.oO%'[part]
        block_chr = '#'

    else:
        block_chr = u'\u2588'
        # there are 8 unicode characters for vertical-bars/horiz-bars
        part = int(part * 8)

        # unicode 0x2581 -> 2589 are vertical bar chunks, like rainbarf uses
        # and following are narrow -> wider bars
        part = unichr(0x258f - part) # for smooth bar
        # part = unichr(0x2581 + part) # for neater-looking thing

    # hack for 100+ full so we don't print extra really-narrow/high bar
    if percent >= 100.0:
        part = ''
    curr = int(curr)
    return '[%s%s%s]' % ((block_chr * curr), part, (' ' * (size - curr - 1)))


def wrap(text, width, prefix=''):
    """
    Simple word-wrapping thing. Might be worth considering a
    dependency on 'textwrap' if this gets longer than a few lines ;)
    """
    words = text.split()
    lines = []
    while len(words):
        line = prefix
        while len(words) and len(line) < width:
            word = words.pop(0)
            line += ' ' + word
        lines.append(line)
    return '\n'.join(lines)

def format_net_location(loc, verbose_asn=False):
    rtn = '(%s ' % loc.ip
    comma = False
    if loc.asn:
        if verbose_asn:
            rtn += loc.asn
        else:
            rtn += loc.asn.split()[0]
        comma = True
    if loc.countrycode:
        if comma:
            rtn += ', '
        rtn += loc.countrycode
        comma = True
    if loc.city and loc.city[0]:
        if comma:
            rtn += ', '
        rtn += ','.join([x.decode('utf8', 'replace') for x in loc.city])
        comma = True
    return rtn.strip() + ')'


def nice_router_name(router, color=True):
    """
    returns a router name with ~ at the front if it's not a named router
    """
    green = str
    italic = str
    if color:
        green = colors.green
        italic = colors.italic
    if router.name_is_unique:
        return green(router.name)
    return italic('~%s' % router.name)


def dump_circuits(state, verbose, show_countries=False):
    print('  %-4s | %-5s | %-42s | %-8s | %-12s' % ('ID', 'Age', 'Path (router names, ~ means no Named flag)', 'State', 'Purpose'))
    print(' ------+-------+' + ('-'*44) + '+' + (10*'-') + '+' + (12*'-'))
    circuits = state.circuits.values()
    circuits.sort(lambda a, b: cmp(a.id, b.id))
    now = datetime.datetime.utcnow()
    for circ in circuits:
        path = '->'.join([nice_router_name(x) for x in circ.path])
        plain_router_name = functools.partial(nice_router_name, color=False)
        plain_path = '->'.join([plain_router_name(x) for x in circ.path])#map(plain_router_name, circ.path))
        real_len = len(plain_path)
        if real_len > 42:
            # revert to uncoloured path since we don't know where ANSI controls are
            path = plain_path[:(42 - 13)] + '...' + plain_path[-10:]
        elif len(path) == 0:
            path = '(empty)'
        else:
            path = path + ((42 - real_len) * ' ')
        age = circ.age(now)
        if age > 300:
            age = '%2dmin' % (age/60.0)
        else:
            age = '%ds' % age

        # path is already padded to 42 chars, as it contains ANSI controls
        print(colors.bold('  %4d | %5s | %s | %-8s | %-12s' % (circ.id, age, path, circ.state, circ.purpose)))
        #print str(circ.flags)
        if show_countries:
            print(' '*17, '->'.join(map(lambda x: x.location.countrycode, circ.path)))
        if verbose:
            padding = ' ' * 17
            print(' ' * 8, ', '.join([(str(k) + '=' + str(v)) for (k, v) in circ.flags.items()]))
            for router in circ.path:
                if router.ip != 'unknown':
                    print(padding, '%s=%s' % (router.name,
                                              format_net_location(router.location)))
    print(' ------+-------+' + ('-'*44) + '+' + (10*'-') + '+' + (12*'-'))

