"""Define an app for working with Alexa."""
from typing import Tuple

from const import CONF_PEOPLE
from core import Base
from helpers import (
    grammatical_list_join,
    relative_search_dict,
    relative_search_list,
    random_affirmative_response,
)
from util.string import camel_to_underscore


class Alexa(Base):
    """Define a class to represent the app."""

    def configure(self) -> None:
        """Configure."""
        self.register_endpoint(self._alexa_endpoint, "alexa")

    def _alexa_endpoint(self, data: dict) -> Tuple[dict, int]:
        """Define an API endpoint to pull Alexa intents."""
        intent = self.get_alexa_intent(data)

        self.log("Received Alexa intent: %s", intent)

        if intent is None:
            message = f"Alexa error encountered: {self.get_alexa_error(data)}"
            response = {"status": "error", "message": message}

            self.error(message)

            return response, 502

        try:
            method = camel_to_underscore(intent)
            speech, card, title = getattr(self, method)(data)
            response = self.format_alexa_response(speech=speech, card=card, title=title)
        except AttributeError as exc:
            self.error(str(exc))
            speech = f"I'm sorry, the {intent} app does not exist."
            response = self.format_alexa_response(speech=speech)

        self.log("Answering: %s", speech)

        return response, 200

    def clean_full_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the CleanFullIntent."""
        containers = {
            "Wolfie": self.wolfie.bin_state.value,
            "The vacuum": self.wolfie.bin_state.value,
            "The dishwasher": self.dishwasher.state.value,
        }

        container = self.get_alexa_slot_value(data, "Container")
        name, state = relative_search_dict(containers, container)

        if name:
            speech = f"{name} is {state.lower()}."
        else:
            speech = f"I don't know what {container} is."

        return speech, speech, f"What state is {container}?"

    def empty_container_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the EmptyContainerIntent."""
        containers = ["Wolfie", "The vacuum", "The dishwasher"]

        container = self.get_alexa_slot_value(data, "Container")
        name = relative_search_list(containers, container)

        if name in ("Wolfie", "The vacuum"):
            self.wolfie.bin_state = self.wolfie.BinStates.empty
            speech = random_affirmative_response()
        elif name == "The dishwasher":
            self.dishwasher.state = self.dishwasher.States.dirty
            speech = random_affirmative_response()
        else:
            speech = f"I don't know what {container} is."

        return speech, speech, f"What state is {container}?"

    def in_next_trash_pickup_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the InNextTrashPickupIntent intent."""
        _, speech = self.trash_manager.in_next_pickup_str()

        return speech, speech, "In the Next Trash Pickup"

    def is_house_secure_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the IsHouseSecureIntent intent."""
        open_entities = self.security_manager.get_insecure_entities()
        if open_entities:
            speech = (
                "These entry points are insecure: "
                f"{grammatical_list_join(open_entities)}."
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
                speech = f"{name} is at {current_moisture}% and doing great!"
            else:
                speech = f"{name} is at {current_moisture}% moisture; I would water it!"
        else:
            speech = f"I couldn't find moisture information for {plant}."
            title = title.format(plant)

        return speech, speech, title

    def run_wolfie_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the StartWolfieIntent intent."""
        action = self.get_alexa_slot_value(data, "Action")
        if action in ("activate", "run", "start"):
            speech = "Go get those dust bunnies, little guy!"
            self.wolfie.start()
        else:
            speech = "Time to go home, vacuum hero!"
            self.wolfie.stop()
        return speech, speech, "Wolfie"

    def where_is_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the WhereIsIntent intent."""
        person_map = {
            "Aaron": "Aaron",
            "Brit": "Britt",
            "Britt": "Britt",
            "Brittany": "Britt",
        }

        slot_value = self.get_alexa_slot_value(data, "First_Name")
        _, first_name = relative_search_dict(person_map, slot_value)

        try:
            person = next(
                (
                    person
                    for person in self.global_vars[CONF_PEOPLE]
                    if person.first_name.lower() == first_name.lower()
                )
            )
        except StopIteration:
            speech = f"I couldn't find a person named {first_name}."
        else:
            speech = f"{person.first_name} is near {person.geocoded_location}."

        return speech, speech, "Where Is?"
