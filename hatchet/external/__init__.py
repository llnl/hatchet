# Copyright 2017-2023 Lawrence Livermore National Security, LLC and other
# Hatchet Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: MIT

# Roundtrip, which powers the interactive Jupyter visualizations in hatchet.vis,
# is loaded lazily on first access to ``hatchet.external.Roundtrip`` (e.g., by
# ``%load_ext hatchet.vis.loader``). Every ``import hatchet`` imports this
# package (for console.py), and loading Roundtrip there printed
# "<IPython.core.display.Javascript object>" or a version warning when hatchet
# was used from a terminal.


class VersionError(Exception):
    """
    Define a version error class with the same features of the base exception class.
    Allows us to catch the very specific ipython version error and throw a warning.
    """

    pass


def _load_roundtrip():
    """
    Import the Roundtrip singleton, or return None if it cannot be loaded.
    """
    try:
        import IPython

        # Testing IPython version
        if int(IPython.__version__.split(".")[0]) > 7:
            raise VersionError()

        from .roundtrip.roundtrip.manager import Roundtrip

    except ImportError:
        return None

    except VersionError:
        if IPython.get_ipython() is not None:
            print(
                "Warning: Roundtrip module could not be loaded. Requires jupyter notebook version <= 7.x."
            )
        return None

    return Roundtrip


# Set after a failed load so Roundtrip is tried, and any warning printed, only
# once per process, as before. This matters because ``from hatchet.external
# import Roundtrip`` looks up a missing name twice.
_roundtrip_unavailable = False


def __getattr__(name):
    # Called only for names not already defined in this module (PEP 562).
    global _roundtrip_unavailable

    if name == "Roundtrip" and not _roundtrip_unavailable:
        roundtrip = _load_roundtrip()
        if roundtrip is not None:
            # Cache it so later lookups find it without coming back here.
            globals()["Roundtrip"] = roundtrip
            return roundtrip
        _roundtrip_unavailable = True

    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
