"""Definetoo-few-public-methods an app for working with Alexa."""

# pylint: disable=attribute-defined-outside-init,unused-argument

import random
from typing import Tuple

from automation import Base  # type: ignore
from const import PEOPLE  # type: ignore
from util import grammatical_list_join, relative_search_dict  # type: ignore
from util.string import camel_to_underscore   # type: ignore


class Alexa(Base):
    """Define a class to represent the app."""

    AFFIRMATIVE_RESPONSES = [
        '10 4.', 'Affirmative.', 'As you decree, so shall it be.',
        'As you wish.', 'By your command.', 'Consider it done.', 'Done.',
        'I can do that.', 'If you insist.', 'It shall be done.',
        'Leave it to me.', 'No Problem.', 'No worries.', 'OK.', 'Roger that.',
        'So say we all.', 'Sure.', 'Will do.', 'You got it.'
    ]

    # --- INITIALIZERS --------------------------------------------------------
    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.appliance_state_info = {
            'The Dishwasher': (
                self.dishwasher, 'state', self.dishwasher.States.dirty),
            'Wolfie': (self.wolfie, 'bin_state', self.wolfie.BinStates.empty),
            'The Vacuum': (
                self.wolfie, 'bin_state', self.wolfie.BinStates.empty)
        }

        self.register_endpoint(self._alexa_endpoint, 'alexa')

    # --- ENDPOINTS -----------------------------------------------------------
    def _alexa_endpoint(self, data: dict) -> Tuple[dict, int]:
        """Define an API endpoint to pull Alexa intents."""
        intent = self.get_alexa_intent(data)
        self.log('Received Alexa intent: {}'.format(intent))

        if intent is None:
            response = {
                'status':
                    'error',
                'message':
                    'Alexa error encountered: {}'.format(
                        self.get_alexa_error(data))
            }
            self.log(response)
            return response, 502

        try:
            method = camel_to_underscore(intent)
            speech, card, title = getattr(self, method)(data)
            response = self.format_alexa_response(
                speech=speech, card=card, title=title)
        except AttributeError as exc:
            self.error(str(exc))
            speech = "I'm sorry, the {0} app does not exist.".format(intent)
            response = self.format_alexa_response(speech=speech)

        self.log('Answering: {}'.format(speech), level='DEBUG')
        self.log(response)
        return response, 200

    # --- ALEXA INTENTS -------------------------------------------------------
    def empty_appliance_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the EmptyApplianceIntent intent."""
        appliance = self.get_alexa_slot_value(data, 'Appliance')
        name, attrs = relative_search_dict(
            self.appliance_state_info, appliance)
        app, state_attr, desired_state = attrs

        self.log('Appliance name: {0}'.format(name), level='DEBUG')
        self.log('App: {0}'.format(app), level='DEBUG')
        self.log('State attribute: {0}'.format(state_attr), level='DEBUG')
        self.log('Desired state: {0}'.format(desired_state), level='DEBUG')

        setattr(app, state_attr, desired_state)

        speech = self.random_affirmative_response()
        return speech, speech, '{0} Is {1}'.format(
            name, desired_state.name)  # type: ignore

    def in_next_trash_pickup_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the InNextTrashPickupIntent intent."""
        _, speech = self.trash_manager.in_next_pickup_str()

        return speech, speech, 'In the Next Trash Pickup'

    def is_house_secure_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the IsHouseSecureIntent intent."""
        open_entities = self.security_system.get_insecure_entities()
        if open_entities:
            speech = 'These entry points are insecure: {0}.'.format(
                grammatical_list_join(open_entities))
        else:
            speech = 'The house is secure, captain!'

        return speech, speech, 'Is the House Secure?'

    def plant_moisture_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the PlantMoistureIntent intent."""
        plant_moisture_threshold = 25
        plant_sensors = {
            'Fred': 'sensor.fiddle_leaf_fig_moisture',
            'The Fiddle Leaf Fig': 'sensor.fiddle_leaf_fig_moisture',
        }

        plant = self.get_alexa_slot_value(data, 'Plant')
        name, sensor = relative_search_dict(plant_sensors, plant)

        self.log('Plant name: {0}'.format(name), level='DEBUG')
        self.log('Plant moisture sensor: {0}'.format(sensor), level='DEBUG')

        title = 'Is {0} Moist Enough?'
        if name and sensor:
            current_moisture = self.get_state(sensor)
            title = title.format(name)

            if current_moisture == 'unknown':
                speech = "I'm not sure; check back later."
            elif float(current_moisture) >= plant_moisture_threshold:
                speech = '{0} is at {1}% and doing great!'.format(
                    name, current_moisture)
            else:
                speech = '{0} is at {1}% moisture; I would water it!'.format(
                    name, current_moisture)
        else:
            speech = "I couldn't find moisture information for {0}.".format(
                plant)
            title = title.format(plant)

        return speech, speech, title

    def random_affirmative_response(self) -> str:
        """Return a randomly chosen affirmative response."""
        return random.choice(self.AFFIRMATIVE_RESPONSES)

    def repeat_tts_intent(self, data: dict) -> None:
        """Define a handler for the RepeatTTSIntent intent."""
        self.tts.repeat()

    def where_is_intent(self, data: dict) -> Tuple[str, str, str]:
        """Define a handler for the WhereIsIntent intent."""
        person = self.get_alexa_slot_value(data, 'Person')
        name, _ = relative_search_dict(PEOPLE, person)

        self.log('Person: {0}'.format(person), level='DEBUG')
        self.log('Name: {0}'.format(name), level='DEBUG')

        title = 'Where is {0}?'
        if name:
            title = title.format(name)
            home_state, geo_data = self.presence_manager.locate(name)

            self.log(geo_data)

            if home_state == self.presence_manager.HomeStates.home:
                speech = '{0} is at home.'.format(name)
            else:
                miles = round(float(geo_data['attributes']['distance']), 1)
                time = int(geo_data['state'])

                if miles > 0:
                    speech = (
                        '{0} is {1} mile{2} and {3} minute{4} away from home.'
                    ).format(
                        name, miles, '' if miles == 1 else 's', time, ''
                        if time == 1 else 's')
                else:
                    speech = '{0} is less than a mile from home.'.format(name)
        else:
            _person = person.title()
            speech = "I'm sorry, I don't know who {0} is.".format(_person)
            title = title.format(_person)

        return speech, speech, title
