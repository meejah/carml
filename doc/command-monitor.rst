.. _monitor:

``monitor``
===========

This command will print out information about circuits, streams and/or
address mappings, and continue listening for circuit and stream
events. If you just want the current state, use ``--once`` to exit
after the initial state is dumped out.

If you don't want circuits, pass ``--no-circuits``
(``-c``). Similarily, there are ``--no-streams`` (``-s``),
``--no-guards`` (``-g``) and ``--no-addr`` (``-a``) options.

For even more information, ``--verbose`` (``-v``).

You can also include log messages by passing ``--log-level=INFO``
(``-l``).

Examples
--------

.. code-block:: console

   $ carml monitor
   $ carml monitor --no-guards --log-level=WARN
   $ carml monitor -sga
