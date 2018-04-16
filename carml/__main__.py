#!/usr/bin/env python

# putting this in __main__ allows you to "run" the module; it's a
# magic Python thing.
# e.g., like: python -m carml

import sys
from carml import cli

if __name__ == "__main__":
    cli.carml()
