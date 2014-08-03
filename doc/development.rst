Development
===========

Adding a New Command
--------------------

It is easy to add a new command, even without "adding it" to the carml
source code. See an example command in ``example_extension/carml/command/blam.py``

So, if you ``export PYTHONPATH=path/to/example_extension:$PYTHONPATH``
you should get a "blam" sub-command for carml. Copy/paste the blam.py
to your own path, and replace "blam" with your command name.

Some notes:

 * "run()" should return a Deferred. Doing errback or callback on it
   causes the process to exit. (See ``monitor.py`` for an example of
   how to exit or not depending on options).
 * if your command doesn't show up, make sure that ``python
   path/to/blam.py`` or whatever runs without errors (e.g. syntax etc)
