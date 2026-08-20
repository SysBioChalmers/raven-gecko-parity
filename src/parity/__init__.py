"""Parity tooling for the RAVEN and GECKO MATLAB/Python implementation pairs.

The package answers three questions, one per module group:

* :mod:`parity.inventory` + :mod:`parity.ledger` + :mod:`parity.check` --- *does every
  public function on both sides have a declared parity status?*
* :mod:`parity.mirror` --- *given what I just changed, what needs mirroring on the other side?*
* :mod:`parity.scenarios` --- *do both implementations still produce the same numbers?*
"""

__version__ = "0.1.0"
