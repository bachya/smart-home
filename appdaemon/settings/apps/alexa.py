"""Define an app for working with Alexa."""
from enum import Enum
from typing import Tuple

from .core import Base
from .helpers import (
    grammatical_list_join,
    relative_search_dict,
    random_affirmative_response,
)
from .helpers.string import camel_to_underscore


class Alexa(Base):
    """Define a class to represent the app."""

    def configure(self) -> None:
        """Configure."""
        self.appliance_state_info = {
            "The Dishwasher": (self.dishwasher, "state", self.dishwasher.States.dirty),
            "Wolfie": (self.wolfie, "bin_state", self.wolfie.BinStates.empty),
            "The Vacuum": (self.wolfie, "bin_state", self.wolfie.BinStates.empty),
        }

        self.register_endpoint(self._alexa_endpoint, "alexa")

    def _alexa_endpoint(self, data: dict) -> Tuple[dict, int]:
        """Define an API endpoint to pull Alexa intents."""
        intent = self.get_alexa_intent(data)

        self.log("Received Alexa intent: {0}".format(intent))

        if intent is None:
            message = "Alexa error encountered: {0}".format(self.get_alexa_error(data))
            response = {"status": "error", "message": message}

            self.error(message)

            return response, 502

        try:
            method = camel_to_underscore(intent)
            speech, card, title = getattr(self, method)(data)
            response = self.format_alexa_response(speech=speech, card=card, title=title)
        except AttributeError as exc:
            self.error(str(exc))
            speech = "I'm sorry, the {0} app does not exist.".format(intent)
            response = self.format_alexa_response(speech=speech)

        self.log("Answering: {0}".format(speech))

        return response, 200

    def empty_appliance_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the EmptyApplianceIntent intent."""
        appliance = self.get_alexa_slot_value(data, "Appliance")
        name, attrs = relative_search_dict(self.appliance_state_info, appliance)

        app: Base
        state_attr: str
        desired_state: Enum
        app, state_attr, desired_state = attrs

        setattr(app, state_attr, desired_state)

        speech = random_affirmative_response()
        return (speech, speech, "{0} Is {1}".format(name, desired_state.name))

    def in_next_trash_pickup_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the InNextTrashPickupIntent intent."""
        _, speech = self.trash_manager.in_next_pickup_str()

        return speech, speech, "In the Next Trash Pickup"

    def is_house_secure_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the IsHouseSecureIntent intent."""
        open_entities = self.security_manager.get_insecure_entities()
        if open_entities:
            speech = "These entry points are insecure: {0}.".format(
                grammatical_list_join(open_entities)
            )
        else:
            speech = "The house is secure, captain!"

        return speech, speech, "Is the House Secure?"

    def plant_moisture_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the PlantMoistureIntent intent."""
        plant_moisture_threshold = 25
        plant_sensors = {
            "Fred": "sensor.fiddle_leaf_fig_moisture",
            "The Fiddle Leaf Fig": "sensor.fiddle_leaf_fig_moisture",
        }

        plant = self.get_alexa_slot_value(data, "Plant")
        name, sensor = relative_search_dict(plant_sensors, plant)

        title = "Is {0} Moist Enough?"
        if name and sensor:
            current_moisture = self.get_state(sensor)
            title = title.format(name)

            if current_moisture == "unknown":
                speech = "I'm not sure; check back later."
            elif float(current_moisture) >= plant_moisture_threshold:
                speech = "{0} is at {1}% and doing great!".format(
                    name, current_moisture
                )
            else:
                speech = "{0} is at {1}% moisture; I would water it!".format(
                    name, current_moisture
                )
        else:
            speech = "I couldn't find moisture information for {0}.".format(plant)
            title = title.format(plant)

        return speech, speech, title

    def repeat_tts_intent(self, data: dict) -> None:
        """Define a handler for the RepeatTTSIntent intent."""
        self.tts.repeat()
