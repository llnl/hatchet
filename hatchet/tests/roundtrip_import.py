# Copyright 2017-2023 Lawrence Livermore National Security, LLC and other
# Hatchet Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: MIT

import os
import subprocess
import sys
import types

import pytest

import hatchet
import hatchet.external

ROUNDTRIP_MANAGER = "hatchet.external.roundtrip.roundtrip.manager"
ROUNDTRIP_WARNING = "Warning: Roundtrip module could not be loaded"

# Stands in for an IPython terminal session with IPython >= 8, so the
# corresponding test runs even where IPython is not installed.
SIMULATED_IPYTHON_TERMINAL = (
    "import sys, types\n"
    "ipython = types.ModuleType('IPython')\n"
    "ipython.__version__ = '9.0.0'\n"
    "ipython.get_ipython = lambda: object()\n"
    "sys.modules['IPython'] = ipython\n"
)


def _fake_ipython(monkeypatch, version, shell):
    """Install a stand-in IPython module, or hide IPython if version is None."""
    ipython = None
    if version is not None:
        ipython = types.ModuleType("IPython")
        ipython.__version__ = version
        ipython.get_ipython = lambda: shell
    monkeypatch.setitem(sys.modules, "IPython", ipython)


@pytest.fixture
def unloaded_roundtrip(monkeypatch):
    """Make hatchet.external act as if nothing has asked for Roundtrip yet."""
    namespace = vars(hatchet.external)
    saved = namespace.pop("Roundtrip", None)
    monkeypatch.setattr(hatchet.external, "_roundtrip_unavailable", False)
    yield
    namespace.pop("Roundtrip", None)
    if saved is not None:
        namespace["Roundtrip"] = saved


@pytest.mark.parametrize(
    "launcher", ["python", "simulated-ipython-terminal", "ipython-terminal"]
)
def test_import_hatchet_prints_nothing(launcher):
    # Importing hatchet from a terminal used to print
    # "<IPython.core.display.Javascript object>" (IPython <= 7) or the Roundtrip
    # warning (IPython terminal with IPython >= 8). See llnl/hatchet#146.
    command = [sys.executable]
    code = "import sys; import hatchet; assert {!r} not in sys.modules".format(
        ROUNDTRIP_MANAGER
    )
    if launcher == "simulated-ipython-terminal":
        code = SIMULATED_IPYTHON_TERMINAL + code
    elif launcher == "ipython-terminal":
        pytest.importorskip("IPython")
        command += ["-m", "IPython", "--quick", "--no-banner"]

    # Make sure the child process imports the same hatchet as this test run.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(hatchet.__file__)))
    pythonpath = [repo_root, os.environ.get("PYTHONPATH", "")]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, pythonpath)))

    result = subprocess.run(
        command + ["-c", code], capture_output=True, text=True, env=env
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_roundtrip_loads_on_first_access(unloaded_roundtrip, monkeypatch):
    _fake_ipython(monkeypatch, "7.34.0", shell=None)
    manager = types.ModuleType(ROUNDTRIP_MANAGER)
    manager.Roundtrip = object()
    monkeypatch.setitem(sys.modules, ROUNDTRIP_MANAGER, manager)

    from hatchet.external import Roundtrip

    assert Roundtrip is manager.Roundtrip
    # Cached on the package, so later lookups skip the loader.
    assert vars(hatchet.external)["Roundtrip"] is manager.Roundtrip


@pytest.mark.parametrize(
    "version, shell, warns",
    [("9.0.0", object(), True), ("9.0.0", None, False), (None, None, False)],
    ids=["ipython-too-new", "ipython-too-new-no-shell", "no-ipython"],
)
def test_roundtrip_unavailable(
    unloaded_roundtrip, monkeypatch, capsys, version, shell, warns
):
    _fake_ipython(monkeypatch, version, shell)

    # Ask twice, as repeated "%load_ext hatchet.vis.loader" calls would.
    for _ in range(2):
        with pytest.raises(ImportError):
            from hatchet.external import Roundtrip  # noqa: F401
    assert not hasattr(hatchet.external, "Roundtrip")

    printed = capsys.readouterr().out.splitlines()
    if warns:
        # Printed once, not on every attempt.
        assert len(printed) == 1 and printed[0].startswith(ROUNDTRIP_WARNING)
    else:
        assert printed == []
