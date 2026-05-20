"""Model emulation subsystem for Scalable (Phase 5).

This package provides scientific model emulation capabilities including:

* :class:`EmulatorRegistry` — manage trained surrogate models
* :func:`emulatable` — decorator marking functions as emulation-capable
* :class:`EmulatorDispatch` — uncertainty-aware routing
* :class:`ActiveLearner` — intelligent scenario selection
* Surrogate model abstractions (GP, RF, gradient boosting)
"""

from __future__ import annotations

from .active_learning import ActiveLearner
from .decorator import emulatable
from .dispatch import EmulatorDispatch, EmulatorDispatchResult
from .registry import EmulatorInfo, EmulatorRegistry
from .surrogate import (
    EmulatorMetadata,
    EmulatorPrediction,
    GradientBoostingEmulator,
    RandomForestEmulator,
    TrainedEmulator,
)
from .uncertainty import CalibrationResult, calibrate_emulator

__all__ = [
    "ActiveLearner",
    "CalibrationResult",
    "EmulatorDispatch",
    "EmulatorDispatchResult",
    "EmulatorInfo",
    "EmulatorMetadata",
    "EmulatorPrediction",
    "EmulatorRegistry",
    "GradientBoostingEmulator",
    "RandomForestEmulator",
    "TrainedEmulator",
    "calibrate_emulator",
    "emulatable",
]
