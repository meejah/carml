.. _circ:

``circ``
========

Play with your circuits. You can do a few main actions:

 * ``--list`` (``-L``) list the current circuits (similar to ``carml monitor``).
 * ``--build`` (``-b``) build a new circuit, either specifying relays by hand or "auto" to let Tor select. You may also use a ``*`` as a stand-in for any positional circuit; only Guards will be selected for the first one.
 * ``--delete`` to delete a circuit (pass ``--if-unused`` or ``-u`` to only delete it after it's no longer used).

The ``~`` characters in the names means that router doesn't have the "Named" flag.

Examples
--------

.. sourcecode::
   console

   $ carml circ --build *,*,AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
   Building circuit: ~whatever->~somerandomrouter->~router_with_all_As
   Circuit ID 83: ~whatever->~somerandomrouter->~router_with_all_As: built.
   $ carml circ --build auto
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   Building new circuit, letting Tor select the path.
   Circuit ID 982: carmlfake0->ryro->nationalliberal: built.   
   $ carml circ --build nationalliberal,ryro,nationalliberal                                                                       
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   Circuit ID 983: nationalliberal->ryro: failed (DESTROYED, TORPROTOCOL).
   $ carml circl --list
   Connected to a Tor version "0.2.4.21 (git-c5a648cc6f218339)" (status: recommended).
   Circuits:
      977: BUILT 10 minutes ago ~carmlfake0->kasperskytor01->~Unnamed
      978: BUILT 10 minutes ago ~carmlfake0->~Unnamed->persladange2
      982: BUILT a minute ago ~carmlfake0->ryro->~nationalliberal

