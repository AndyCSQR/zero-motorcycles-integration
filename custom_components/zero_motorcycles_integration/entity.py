"""ZeroEntity class."""
from __future__ import annotations

import json
import os

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import LOGGER
from .coordinator import ZeroCoordinator


class ZeroEntity(CoordinatorEntity):
    """Zero Entity class."""

    _attr_attribution = "Zero Motorcycles Integration"

    def __init__(self, coordinator: ZeroCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        # get data from manifest here instead, is this the way to go?
        # mostly done so we wouldn't have to change version in several places
        info = json.load(
            open(f"{os.path.dirname(os.path.realpath(__file__))}/manifest.json")
        )
        LOGGER.debug("loaded info %s", info)
