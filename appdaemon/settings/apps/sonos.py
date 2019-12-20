"""Define an app to manage our Sonos players."""
from typing import List, Optional

from core import Base


class SonosSpeaker(Base):
    """Define a class to represent a Sonos speaker."""

    def configure(self) -> None:
        """Configure."""
        self._last_snapshot_included_group = False
        self.sonos_manager.register_entity(self)

    def __str__(self) -> str:
        """Define a string representation of the speaker."""
        return self.entity_ids["speaker"]

    @property
    def default_volume(self) -> float:
        """Return the audio player's default volume."""
        return self.properties["default_volume"]

    @property
    def volume(self) -> float:
        """Retrieve the audio player's volume."""
        return float(
            self.get_state(self.entity_ids["speaker"], attribute="volume_level")
        )

    @volume.setter
    def volume(self, value: float) -> None:
        """Set the audio player's volume."""
        self.call_service(
            "media_player/volume_set",
            entity_id=self.entity_ids["speaker"],
            volume_level=value,
        )

    def pause(self) -> None:
        """Pause."""
        self.call_service(
            "media_player/media_pause", entity_id=self.entity_ids["speaker"]
        )

    def play(self) -> None:
        """Play."""
        self.call_service(
            "media_player/media_play", entity_id=self.entity_ids["speaker"]
        )

    def play_file(self, url: str) -> None:
        """Play an audio file at a defined URL."""
        self.call_service(
            "media_player/play_media",
            entity_id=self.entity_ids["speaker"],
            media_content_id=url,
            media_content_type="MUSIC",
        )

    def restore(self) -> None:
        """Restore the previous snapshot of this entity."""
        self.call_service(
            "media_player/sonos_restore",
            entity_id=self.entity_ids["speaker"],
            with_group=self._last_snapshot_included_group,
        )

    def snapshot(self, include_grouping: bool = True) -> None:
        """Snapshot this entity."""
        self._last_snapshot_included_group = include_grouping
        self.call_service(
            "media_player/sonos_snapshot",
            entity_id=self.entity_ids["speaker"],
            with_group=include_grouping,
        )


class SonosManager(Base):
    """Define a class to represent the Sono manager."""

    def configure(self) -> None:
        """Configure."""
        self._last_snapshot_included_group = False
        self.speakers = []  # type: List[SonosSpeaker]

    def group(self, entity_list: List[SonosSpeaker] = None) -> Optional[SonosSpeaker]:
        """Group a list of speakers together (default: all)."""
        if entity_list:
            entities = entity_list
        else:
            entities = self.entity_ids

        if len(entities) == 1:
            self.error("Refusing to group only one Sonos speaker", level="WARNING")
            return None

        master = entities[0]

        self.call_service(
            "media_player/sonos_join",
            master=master.entity,
            entity_id=[str(e) for e in entities],
        )

        return master

    def register_entity(self, speaker_object: SonosSpeaker) -> None:
        """Register a Sonos entity object."""
        if speaker_object in self.speakers:
            self.log("Entity already registered; skipping: %s", speaker_object)
            return

        self.speakers.append(speaker_object)

    def restore_all(self) -> None:
        """Restore the previous snapshot of all speakers."""
        self.call_service(
            "media_player/sonos_restore",
            entity_id=[str(e) for e in self.speakers],
            with_group=self._last_snapshot_included_group,
        )

    def set_all_volume(self) -> None:
        """Set the volume correctly."""
        for speaker in self.speakers:
            speaker.volume = speaker.default_volume

    def snapshot_all(self, include_grouping: bool = True) -> None:
        """Snapshot all registered speakers simultaneously."""
        self._last_snapshot_included_group = include_grouping
        self.call_service(
            "media_player/sonos_snapshot",
            entity_id=[str(e) for e in self.speakers],
            with_group=include_grouping,
        )

    def ungroup_all(self) -> None:
        """Return all speakers to "individual" status."""
        self.call_service(
            "media_player/sonos_unjoin", entity_id=[str(e) for e in self.speakers]
        )
