"""Define an app to manage our Sonos players."""

# pylint: disable=attribute-defined-outside-init

from typing import Union

from automation import Base  # type: ignore


class SonosSpeaker(Base):
    """Define a class to represent a Sonos speaker."""

    @property
    def default_volume(self) -> float:
        """Return the audio player's default volume."""
        return self.properties['default_volume']

    @property
    def volume(self) -> float:
        """Retrieve the audio player's volume."""
        return float(
            self.get_state(self.entities['speaker'], attribute='volume_level'))

    @volume.setter
    def volume(self, value: float) -> None:
        """Set the audio player's volume."""
        self.call_service(
            'media_player/volume_set',
            entity_id=self.entities['speaker'],
            volume_level=value)

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self._last_snapshot_included_group = False
        self.sonos_manager.register_entity(self)

    def __str__(self) -> str:
        """Define a string representation of the speaker."""
        return self.entities['speaker']

    def pause(self) -> None:
        """Pause."""
        self.call_service(
            'media_player/media_pause', entity_id=self.entities['speaker'])

    def play(self) -> None:
        """Play."""
        self.call_service(
            'media_player/media_play', entity_id=self.entities['speaker'])

    def play_file(self, url: str) -> None:
        """Play an audio file at a defined URL."""
        self.call_service(
            'media_player/play_media',
            entity_id=self.entities['speaker'],
            media_content_id=url,
            media_content_type='MUSIC')

    def restore(self) -> None:
        """Restore the previous snapshot of this entity."""
        self.call_service(
            'media_player/sonos_restore',
            entity_id=self.entities['speaker'],
            with_group=self._last_snapshot_included_group)

    def snapshot(self, include_grouping: bool = True) -> None:
        """Snapshot this entity."""
        self._last_snapshot_included_group = include_grouping
        self.call_service(
            'media_player/sonos_snapshot',
            entity_id=self.entities['speaker'],
            with_group=include_grouping)


class SonosManager(Base):
    """Define a class to represent the Sono manager."""

    def initialize(self) -> None:
        """Initialize."""
        self._last_snapshot_included_group = False
        self.speakers = []  # type: ignore

        super().initialize()

    def group(self, entity_list: list = None) -> Union[SonosSpeaker, None]:
        """Group a list of speakers together (default: all)."""
        entities = entity_list
        if not entity_list:
            entities = [entity for entity in self.entities]

        master = entities.pop(0)  # type: ignore

        if not entities:
            self.log(
                'Refusing to group only one entity: {0}'.format(master),
                level='WARNING')
            return None

        self.call_service(
            'media_player/sonos_join',
            master=master.entity,
            entity_id=[str(e) for e in entities])

        return master

    def register_entity(self, speaker_object: SonosSpeaker) -> None:
        """Register a Sonos entity object."""
        if speaker_object in self.speakers:
            self.log(
                'Entity already registered; skipping: {0}'.format(
                    speaker_object))
            return

        self.speakers.append(speaker_object)

    def restore_all(self) -> None:
        """Restore the previous snapshot of all speakers."""
        self.call_service(
            'media_player/sonos_restore',
            entity_id=[str(e) for e in self.speakers],
            with_group=self._last_snapshot_included_group)

    def set_all_volume(self) -> None:
        """Set the volume correctly."""
        for speaker in self.speakers:
            speaker.volume = speaker.default_volume

    def snapshot_all(self, include_grouping: bool = True) -> None:
        """Snapshot all registered speakers simultaneously."""
        self._last_snapshot_included_group = include_grouping
        self.call_service(
            'media_player/sonos_snapshot',
            entity_id=[str(e) for e in self.speakers],
            with_group=include_grouping)

    def ungroup_all(self) -> None:
        """Return all speakers to "individual" status."""
        self.call_service(
            'media_player/sonos_unjoin',
            entity_id=[str(e) for e in self.speakers])
