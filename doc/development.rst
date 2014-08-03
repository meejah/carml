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

 * you are responsible for ensuring ``reactor.stop()`` gets called if you
   want your command to exit.
 * alternatively, if "run()" returns a Deferred, that Deferred doing
   errback or callback causes the process to exit.
 * if your command doesn't show up, make sure that ``python
   path/to/blam.py`` or whatever runs without errors (e.g. syntax etc)
