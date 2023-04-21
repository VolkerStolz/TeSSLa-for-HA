import time
import threading
import subprocess
import logging

# from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_state_change

# TODO: What's the HA-way of finding the path to those files?
tessla_spec_file = "homeassistant/components/tessla/specification.tessla"
tessla_jar_file = "homeassistant/components/tessla/tessla.jar"

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    # Start the TeSSLa interpreter process with the given specification file.
    tessla_process = subprocess.Popen(
        ["java", "-jar", tessla_jar_file, "interpreter", tessla_spec_file],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,  # Linebuffer!
        universal_newlines=True,
    )
    _LOGGER.info("Tessla started")

    def tlogger():
        for e in tessla_process.stderr:
            _LOGGER.error(f"Tessla failed: {e}")
    threading.Thread(target=tlogger).start()
    ms = MySensor(hass, tessla_process)
    add_entities([ms])
    # Create a separate thread to read and print the TeSSLa output.
    # DON'T START IT YET to avoid race condition
    # ms.set_output_thread(threading.Thread(target=ms.vs2))
    ms.set_output_thread(threading.Thread(target=ms.vs))


class MySensor(SensorEntity):

    _attr_should_poll = False

    def __init__(self, hass, process):
        self._state = "-1"
        self._hass = hass
        self.tessla = process
        self.j = 1
        self.t = None
        self.running = False

        # Register a state change listener for the "sensor.random_sensor" entity
        async_track_state_change(
           hass, "sensor.random_sensor", self._async_state_changed
        )

    def set_output_thread(self, t):
        self.t = t

    @property
    def name(self):
        return "tessla"

    @property
    def state(self):
        if not self.running and self.t is not None:
            self.t.start()
            self.running = True
        return self._state

    def vs2(self):
        i = 0
        while True:
            line = f"{i}\n"
            _LOGGER.error(f"vs: {i}")
            self._state = str(i)
            self.schedule_update_ha_state()
            i = i + 1
            time.sleep(1)

    def vs(self):
        _LOGGER.info(f"Waiting for Tessla output.")
        for line in self.tessla.stdout:
            _LOGGER.info(f"Tessla said: {line.strip()}.")
            self._state = line.strip()
            self.schedule_update_ha_state()
            _LOGGER.info(f"Waiting for Tessla output.")

    async def _async_state_changed(self, entity_id, old_state, new_state):
        if new_state is None:
            return
        self.tessla.stdin.write(f"{self.j}: x = {self.j}\n")
        _LOGGER.info(f"Tessla notified, value: {new_state}")
        self.j = self.j + 1
