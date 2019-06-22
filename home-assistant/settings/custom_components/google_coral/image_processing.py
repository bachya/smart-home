"""Support for Google Coral image processing."""
import logging

import voluptuous as vol

from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA,
    ImageProcessingEntity,
    CONF_CONFIDENCE,
    CONF_SOURCE,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_IP_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.core import split_entity_id
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_TARGET = "target"
ATTR_PREDICTIONS = "predictions"
ATTR_CONFIDENCE = "confidence"

CONF_TARGET_OBJECT = "target_object"

DEFAULT_CLASSIFIER = "google_coral"
DEFAULT_TARGET_OBJECT = "person"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_TARGET_OBJECT, default=DEFAULT_TARGET_OBJECT): cv.string,
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the classifier."""
    ip_address = config[CONF_IP_ADDRESS]
    port = config[CONF_PORT]
    target = config[CONF_TARGET_OBJECT]
    confidence = config[CONF_CONFIDENCE]

    add_devices(
        [
            ObjectClassifyEntity(
                ip_address,
                port,
                target,
                confidence,
                camera[CONF_ENTITY_ID],
                camera.get(CONF_NAME),
            )
            for camera in config[CONF_SOURCE]
        ]
    )


class ObjectClassifyEntity(ImageProcessingEntity):
    """Construct a Google Coral object classifier."""

    def __init__(self, ip_address, port, target, confidence, camera_entity, name=None):
        """Initialize."""
        self._attrs = {ATTR_TARGET: target}
        self._camera = camera_entity
        self._confidence = confidence
        self._predictions = {}
        self._state = None
        self._target = target
        self._url_predict = "http://{0}:{1}/predict".format(ip_address, port)

        if name:
            self._name = "{0}_{1}".format(name, self._target)
        else:
            camera_name = split_entity_id(camera_entity)[1]
            self._name = "{0}_{1}_{2}".format(
                DEFAULT_CLASSIFIER, camera_name, self._target
            )

    @property
    def camera_entity(self):
        """Return the camera entity being processed."""
        return self._camera

    @property
    def device_state_attributes(self):
        """Return device-specific state attributes."""
        return self._attrs

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    async def async_process_image(self, image):
        """Process image."""
        from aiohttp.client_exceptions import ClientError

        websession = aiohttp_client.async_get_clientsession(self.hass)

        async with websession.request(
            "post", self._url_predict, data={"image": image}
        ) as resp:
            try:
                resp.raise_for_status()
                data = await resp.json()
            except ClientError as err:
                _LOGGER.error(
                    "Error requesting data from %s: %s", self._url_predict, err
                )
                return

            if not data["success"]:
                _LOGGER.error("Error processing image: %s", data["message"])

            _LOGGER.info(data["message"])
            _LOGGER.debug("Image data received (%s): %s", self._name, data)

            predictions = [
                p for p in data["data"] if float(p["confidence"]) >= self._confidence
            ]

            targets = [t for t in predictions if t["label"] == self._target]

            self._attrs.update(
                {
                    ATTR_CONFIDENCE: [t["confidence"] for t in targets],
                    ATTR_PREDICTIONS: [p["label"] for p in predictions],
                }
            )
            self._state = len(targets)
