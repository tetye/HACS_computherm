import broadlink
import logging
import time
import asyncio
from datetime import datetime

from homeassistant.const import (
    PRECISION_HALVES
)

_LOGGER = logging.getLogger(__name__)

BROADLINK_ACTIVE = 1
BROADLINK_IDLE = 0
BROADLINK_POWER_ON = 1
BROADLINK_POWER_OFF = 0
BROADLINK_MODE_MANUAL = 0
BROADLINK_MODE_AUTO = 1
BROADLINK_SENSOR_INTERNAL = 0
BROADLINK_SENSOR_EXTERNAL = 1
BROADLINK_SENSOR_BOTH = 2
BROADLINK_TEMP_AUTO = 0
BROADLINK_TEMP_MANUAL = 1

CONF_HOST = 'host'
CONF_USE_EXTERNAL_TEMP = 'use_external_temp'
CONF_SCHEDULE = 'schedule'
CONF_UNIQUE_ID = 'unique_id'
CONF_PRECISION = 'precision'
CONF_USE_COOLING = 'use_cooling'

DEFAULT_SCHEDULE = 0
DEFAULT_USE_EXTERNAL_TEMP = True
DEFAULT_PRECISION = PRECISION_HALVES
DEFAULT_USE_COOLING = False


class BroadlinkThermostat:

    def __init__(self, host, port=80):
        self._host = host
        self._port = port

    def _device(self):
        max_attempt = 3
        for attempt in range(0, max_attempt):
            try:
                attempt += 1
                return broadlink.hello(self._host, port=self._port, timeout=3)
            except TypeError:
                return broadlink.hello(self._host, timeout=3)
            except broadlink.exceptions.NetworkTimeoutError as e:
                if attempt == max_attempt:
                    _LOGGER.error("Thermostat %s network error: %s", self._host, str(e))
        raise AssertionError("Thermostat discovery exhausted retries")
    async def run(self, func):
        return await asyncio.to_thread(lambda: func(self._device()))

    async def set_time(self):
        """Set thermostat time"""
        try:
            def _apply(device):
                if device.auth():
                    now = datetime.now()
                    device.set_time(now.hour, now.minute, now.second, now.weekday() + 1)
            await self.run(_apply)
            _LOGGER.debug("Thermostat date / time is set")
        except Exception as e:
            _LOGGER.error("Thermostat %s set_time error: %s", self._host, str(e))

    async def read_status(self):
        """Read thermostat data"""
        try:
            def _apply(device):
                if device.auth():
                    return device.get_full_status()
                return None
            data = await self.run(_apply)
            _LOGGER.debug("Received %s thermostat data: %s", self._host, data)
            return data
        except Exception as e:
            _LOGGER.warning("Thermostat %s read_status() error: %s", self._host, str(e))
            return None
