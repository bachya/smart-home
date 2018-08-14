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
        constraint = self.args.get('constraint')

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
                self, name, {
                    **self.entities,
                    **feature.get('entities', {})
                }, {
                    **self.properties,
                    **feature.get('properties', {})
                }, feature.get('constraint', constraint),
                feature.get('mode_alterations', {}))

            if not feature_obj.repeatable and feature_obj in features:
                self.error(
                    'Refusing to reinitialize single feature: {0}'.format(
                        name))
                continue

            self.log(
                'Initializing feature {0} (constraint: {1})'.format(
                    name, feature_obj.constraint))

            features.append(feature_obj)
            feature_obj.initialize()


class Feature:
    """Define an automation feature."""

    def __init__(  # pylint: disable=too-many-arguments
            self,
            hass: Automation,
            name: str,
            entities: dict = None,
            properties: dict = None,
            constraint_config: dict = None,
            mode_alterations: dict = None) -> None:
        """Initiliaze."""
        self.entities = entities
        self.handles = {}  # type: ignore
        self.hass = hass
        self.name = name
        self.properties = properties

        if constraint_config:
            if constraint_config.get('key'):
                self.constraint = 'input_boolean.{0}_{1}'.format(
                    hass.name, constraint_config['key'])
            else:
                self.constraint = 'input_boolean.{0}_{1}'.format(
                    hass.name, name)
        else:
            self.constraint = None  # type: ignore

        if mode_alterations:
            for mode, value in mode_alterations.items():
                mode_app = getattr(self.hass, mode)
                mode_app.register_constraint_alteration(self.constraint, value)

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

    def listen_ios_event(self, callback: Callable, action: str) -> None:
        """Register a callback for an iOS event."""
        self.hass.listen_event(
            callback,
            'ios.notification_action_fired',
            actionName=action,
            constrain_input_boolean=self.constraint)
