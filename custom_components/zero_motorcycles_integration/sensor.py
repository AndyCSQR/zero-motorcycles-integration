"""Sensor platform for zero_motorcycles_integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfElectricPotential, UnitOfTime, PERCENTAGE
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, LOGGER
from .coordinator import ZeroCoordinator
from .entity import ZeroEntity

SENSORS = (
    SensorEntityDescription(
        key="zero_motorcycles",
        name="soc",
        icon="mdi:battery-charging-50",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="name",
        icon="mdi:id-card",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="mileage",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="software_version",
        icon="mdi:bug",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="longitude",
        icon="mdi:map-marker",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="latitude",
        icon="mdi:map-marker",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="altitude",
        icon="mdi:image-filter-hdr",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="satellites",
        icon="mdi:satellite-variant",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="velocity",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="heading",
        icon="mdi:compass",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="main_voltage",
        icon="mdi:car-battery",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key="zero_motorcycles",
        name="chargingtimeleft",
        icon="mdi:battery-clock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # create sensors for all units found, not just the first one
    # work with an array of devices
    devices = []

    for unit in coordinator.units:
        for sensor in SENSORS:
            devices.append(
                ZeroSensor(
                    coordinator=coordinator,
                    entity_description=sensor,
                    unitnumber=unit["unitnumber"],
                    sensor_name=sensor.name,
                )
            )

    async_add_devices(devices, True)


class ZeroSensor(ZeroEntity, SensorEntity):
    """zero_motorcycles_integration Sensor class."""

    def __init__(
        self,
        coordinator: ZeroCoordinator,
        entity_description: SensorEntityDescription,
        unitnumber: str,
        sensor_name: str,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)

        # set unit number for unit reference here, this is used as a key in received data
        self.unitnumber = unitnumber
        self.sensor_name = sensor_name  # used for data point reference

        # had to create unique IDs per sensor here, using key.name
        self._attr_unique_id = (
            entity_description.key + "." + unitnumber + "." + entity_description.name
        )
        self._name = f"Zero {unitnumber} {entity_description.name}"

        # Per-unit device info so each bike shows as its own device
        unit_info = next(
            (u for u in coordinator.units if u.get("unitnumber") == unitnumber), {}
        )
        self._attr_device_info = DeviceInfo(
            identifiers={("zero_motorcycles_integration", unitnumber)},
            name=f"Zero {unitnumber}",
            model=f"Zero (unit model {unit_info.get('unitmodel', '?')})",
            manufacturer="Zero Motorcycles",
            serial_number=unit_info.get("name", unitnumber),
        )

        self.entity_description = entity_description

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        value = self.coordinator.data[self.unitnumber][0][self.sensor_name]
        LOGGER.debug(
            "Sensor value for %s is %s (type: %s)",
            self.unique_id,
            value,
            type(value).__name__,
        )

        # Convert values based on sensor type
        sensor_name = self.sensor_name

        # Numeric sensors that may come as strings
        numeric_fields = {
            "mileage", "velocity", "main_voltage", "altitude",
            "chargingtimeleft", "satellites", "heading",
        }
        if sensor_name in numeric_fields:
            try:
                # Try float first, fall back to string if empty
                if value == "" or value is None:
                    return None
                return float(value)
            except (ValueError, TypeError):
                return None

        # Integer fields
        int_fields = {"soc", "battery"}
        if sensor_name in int_fields:
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # String fields
        return value
