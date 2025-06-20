from socket import timeout
from custom_components.computherm import (
    BroadlinkThermostat,
    CONF_HOST,
    CONF_UNIQUE_ID,
    CONF_USE_EXTERNAL_TEMP,
    CONF_USE_EXTERNAL_TEMP,
    DEFAULT_SCHEDULE,
    DEFAULT_USE_EXTERNAL_TEMP,
    BROADLINK_POWER_ON,
    BROADLINK_POWER_OFF,
    BROADLINK_MODE_MANUAL,
    BROADLINK_ACTIVE,
    BROADLINK_SENSOR_EXTERNAL,
    BROADLINK_SENSOR_INTERNAL
)

import logging
_LOGGER = logging.getLogger(__name__)

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity, PLATFORM_SCHEMA
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import (
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_ON,
    STATE_OFF
)
from homeassistant.components.climate.const import (
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP
)

import homeassistant.helpers.config_validation as cv

BROADLINK_TURN_OFF = 'turn_off'
BROADLINK_MIN_TEMP = 'min_temp'
BROADLINK_MAX_TEMP = 'max_temp'

PARALLEL_UPDATES = 0

DEFAULT_TURN_OFF_MODE = BROADLINK_MIN_TEMP
DEFAULT_TURN_ON_MODE = BROADLINK_MAX_TEMP

CONF_TURN_OFF_MODE = 'turn_off_mode'
CONF_TURN_ON_MODE = 'turn_on_mode'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional('port', default=80): cv.port,
    vol.Optional(CONF_USE_EXTERNAL_TEMP, default=DEFAULT_USE_EXTERNAL_TEMP): cv.boolean,
    vol.Optional(CONF_TURN_OFF_MODE, default=DEFAULT_TURN_OFF_MODE): vol.Any(int, float, BROADLINK_MIN_TEMP, BROADLINK_TURN_OFF),
    vol.Optional(CONF_TURN_ON_MODE, default=DEFAULT_TURN_ON_MODE): vol.Any(int, float, BROADLINK_MAX_TEMP)
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform."""
    async_add_entities([ComputhermSwitch(hass, config)])


class ComputhermSwitch(SwitchEntity, RestoreEntity):

    def __init__(self, hass, config):
        self._hass = hass
        self._thermostat = BroadlinkThermostat(config.get(CONF_HOST), config.get('port', 80))

        self._name = config.get(CONF_NAME)
        self._use_external_temp = config.get(CONF_USE_EXTERNAL_TEMP)

        self._min_temp = DEFAULT_MIN_TEMP
        self._max_temp = DEFAULT_MAX_TEMP
        self._room_temp = None
        self._external_temp = None

        self._turn_on_mode = config.get(CONF_TURN_ON_MODE)
        self._turn_off_mode = config.get(CONF_TURN_OFF_MODE)

        if not isinstance(self._turn_off_mode, str) and not isinstance(self._turn_on_mode, str) and self._turn_off_mode > self._turn_on_mode:
            _LOGGER.error("Turn off mode is greater than turn on mode, defaulting to \"min_temp\"")
            self._turn_off_mode = BROADLINK_MIN_TEMP

        self._thermostat_current_temp = None
        self._thermostat_target_temp = None

        self._attr_name = self._name
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)

        self._state = STATE_UNAVAILABLE

    def thermostat_get_sensor(self) -> int:
        """Get sensor to use"""
        return BROADLINK_SENSOR_EXTERNAL if self._use_external_temp is True else BROADLINK_SENSOR_INTERNAL

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return thermostat state on / off"""
        return self._state == STATE_ON

    @property
    def extra_state_attributes(self) -> dict:
        """Return the attribute(s) of the sensor"""
        return {
            'external_temp': self._external_temp,
            'room_temp': self._room_temp,
            'current_temp': self._thermostat_current_temp,
            'target_temp': self._thermostat_target_temp
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to added."""
        await super().async_added_to_hass()

        # Set thermostat time
        self._hass.async_add_executor_job(self._thermostat.set_time)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn  the entity on"""
        device = self._thermostat.device()
        if device.auth():
            device.set_power(BROADLINK_POWER_ON)
            device.set_mode(BROADLINK_MODE_MANUAL, 0, self.thermostat_get_sensor())
            device.set_temp(self._max_temp if self._turn_on_mode == BROADLINK_MAX_TEMP else float(self._turn_on_mode))

        self._state = STATE_ON
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off"""
        device = self._thermostat.device()
        if device.auth():
            if self._turn_off_mode == BROADLINK_TURN_OFF:
                device.set_power(BROADLINK_POWER_OFF)
            else:
                device.set_mode(BROADLINK_MODE_MANUAL, 0, self.thermostat_get_sensor())
                device.set_temp(self._min_temp if self._turn_off_mode == BROADLINK_MIN_TEMP else float(self._turn_off_mode))

        self._state = STATE_OFF
        await self.async_update_ha_state()

    async def async_update(self) -> None:
        """Get thermostat info"""
        data = await self._hass.async_add_executor_job(self._thermostat.read_status)

        if not data:
            self._state = STATE_UNAVAILABLE
            return

        if data['power'] == BROADLINK_POWER_ON and data['active'] == BROADLINK_ACTIVE:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

        self._room_temp = data['room_temp']
        self._external_temp = data['external_temp']

        self._thermostat_current_temp = data['external_temp'] if self._use_external_temp else data['room_temp']
        self._thermostat_target_temp = data['thermostat_temp']

        self._min_temp = int(data['svl'])
        self._max_temp = int(data['svh'])

