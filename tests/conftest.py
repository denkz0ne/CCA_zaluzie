"""Pure engine tests also run on hosts without a Home Assistant installation."""

import importlib.util
import sys
import types
from pathlib import Path

if importlib.util.find_spec("homeassistant") is None:
    package = types.ModuleType("custom_components.cca_zaluzie")
    package.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "cca_zaluzie")]
    sys.modules[package.__name__] = package
