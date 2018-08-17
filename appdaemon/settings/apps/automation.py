"""Define generic automation objects and logic."""

# pylint: disable=attribute-defined-outside-init

import sys
from typing import Callable

from core import Base  # type: ignore
from util import underscore_to_camel  # type: ignore


class Automation(Base):
    """Define a base automation object."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.friendly_name = self.args.get('friendly_name')
        enabled_toggle = self.args.get('enabled_toggle')

        if self.args.get('manager_app'):
            self.manager_app = getattr(self, self.args['manager_app'])

        for feature in self.args.get('features'):
            name = feature['name']

            feature_class = getattr(
                sys.modules[self.args['module']], underscore_to_camel(name),
                None)
            if not feature_class:
                self.log('Missing class for feature: {0}'.format(name))
                continue

            features = []  # type: ignore
            feature_obj = feature_class(
                self,
                name,
                entities={
                    **self.entities,
                    **feature.get('entities', {})
                },
                conditions=feature.get('conditions', {}),
                properties={
                    **self.properties,
                    **feature.get('properties', {})
                },
                enabled_toggle_config=feature.get(
                    'enabled_toggle', enabled_toggle),
                mode_alterations=feature.get('mode_alterations', {}))

            if not feature_obj.repeatable and feature_obj in features:
                self.error(
                    'Refusing to reinitialize single feature: {0}'.format(
                        name))
                continue

            self.log(
                'Initializing feature {0} (enabled_toggle: {1})'.format(
                    name, feature_obj.enabled_toggle))

            features.append(feature_obj)
            feature_obj.initialize()


class Feature:  # pylint: disable=too-many-instance-attributes
    """Define an automation feature."""

    def __init__(  # pylint: disable=too-many-arguments
            self,
            hass: Automation,
            name: str,
            *,
            entities: dict = None,
            conditions: dict = None,
            properties: dict = None,
            enabled_toggle_config: dict = None,
            mode_alterations: dict = None) -> None:
        """Initiliaze."""
        self.conditions = conditions
        self.entities = entities
        self.handles = {}  # type: ignore
        self.hass = hass
        self.name = name
        self.properties = properties

        if enabled_toggle_config:
            if enabled_toggle_config.get('key'):
                self.enabled_toggle = 'input_boolean.{0}_{1}'.format(
                    hass.name, enabled_toggle_config['key'])
            else:
                self.enabled_toggle = 'input_boolean.{0}_{1}'.format(
                    hass.name, name)
        else:
            self.enabled_toggle = None  # type: ignore

        if mode_alterations:
            for mode, value in mode_alterations.items():
                mode_app = getattr(self.hass, mode)
                mode_app.register_enabled_toggle(self.enabled_toggle, value)

    def __eq__(self, other):
        """Define equality based on name."""
        return self.name == other.name

    @property
    def repeatable(self) -> bool:
        """Define whether a feature can be implemented multiple times."""
        return False

    def initialize(self) -> None:
        """Define an initializer method."""
        raise NotImplementedError

    def generate_conditions(self, condition_constraint_map: dict) -> dict:
        """Generate a constraints kwargs list from a mapping."""
        kwargs = {}
        for condition in self.conditions:  # type: ignore
            name, value = condition_constraint_map[condition]
            kwargs[name] = value
        return kwargs

    def listen_ios_event(self, callback: Callable, action: str) -> None:
        """Register a callback for an iOS event."""
        self.hass.listen_event(
            callback,
            'ios.notification_action_fired',
            actionName=action,
            constrain_input_boolean=self.enabled_toggle)
