"""Define an app for working with TTS (over Sonos)."""
from typing import Tuple

from core import Base
from helpers.dt import relative_time_of_day

OPENER_FILE_URL = 'https://hass.myserver.com/local/tts_opener.mp3'


class TTS(Base):
    """Define a class to represent the app."""

    def configure(self) -> None:
        """Configure."""
        self._last_spoken_text = ""
        self.register_endpoint(self._emergency_endpoint, "emergency")
        self.register_endpoint(self._tts_endpoint, "tts")

    def _emergency_endpoint(self, data: dict) -> Tuple[dict, int]:
        """Define an endpoint to alert us of an emergency."""
        if self.presence_manager.noone(self.presence_manager.HomeStates.home):
            return {"status": "ok", "message": "No one home; ignoring"}, 200

        try:
            name = data["name"].title()
        except KeyError:
            return (
                {"status": "error", "message": 'Missing "name" parameter'},
                502,
            )

        self.log("Emergency Notification from {0}".format(name))

        statement = "Please call {0} as soon as possible.".format(name)
        self.speak(statement, iterations=3)
        return {"status": "ok", "message": statement}, 200

    def _tts_endpoint(self, data: dict) -> Tuple[dict, int]:
        """Define an API endpoint to handle incoming TTS requests."""
        if self.presence_manager.noone(self.presence_manager.HomeStates.home):
            return {"status": "ok", "message": "No one home; ignoring"}, 200

        try:
            text = data["text"]
        except KeyError:
            return (
                {"status": "error", "message": 'Missing "text" parameter'},
                502,
            )

        self.log("Received TTS data: {0}".format(data))

        self.speak(text, iterations=data.get("iterations", 1))
        return {"status": "ok", "message": data["text"]}, 200

    def _calculate_ending_duration_cb(self, kwargs: dict) -> None:
        """Calculate how long the TTS should play."""
        master_sonos_player = kwargs["master_sonos_player"]

        duration = self.get_state(
            str(master_sonos_player), attribute="media_duration"
        )
        if not duration:
            self.error("Couldn't calculate ending duration for TTS")
            return

        self.run_in(
            self._end_cb, duration, master_sonos_player=master_sonos_player
        )

    def _end_cb(self, kwargs: dict) -> None:
        """Restore the Sonos to its previous state after speech is done."""
        master_sonos_player = kwargs["master_sonos_player"]

        master_sonos_player.play_file(OPENER_FILE_URL)
        self.run_in(self._restore_cb, 3.25)

    def _restore_cb(self, kwargs: dict) -> None:
        """Restore the Sonos to its previous state after speech is done."""
        if self.living_room_tv.current_activity_id:
            self.living_room_tv.play()
        self.sonos_manager.ungroup_all()
        self.sonos_manager.restore_all()

    def _speak_cb(self, kwargs: dict) -> None:
        """Restore the Sonos to its previous state after speech is done."""
        master_sonos_player = kwargs["master_sonos_player"]
        text = kwargs["text"]

        self.call_service(
            "tts/amazon_polly_say",
            entity_id=str(master_sonos_player),
            message=text,
        )

        self.run_in(
            self._calculate_ending_duration_cb,
            2,
            master_sonos_player=master_sonos_player,
        )

    @staticmethod
    def _calculate_iterated_text(text: str, iterations: int = 1) -> str:
        """Return a string that equals itself times a number of iterations."""
        return " Once again, ".join([text] * iterations)

    def repeat(self, iterations: int = 1) -> None:
        """Repeat the last thing that was spoken."""
        if self._last_spoken_text:
            final_string = self._calculate_iterated_text(
                self._last_spoken_text, iterations
            )

            self.log("Repeating over TTS: {0}".format(final_string))

            self.speak(final_string)

    def speak(self, text: str, iterations: int = 1) -> None:
        """Speak the provided text through the Sonos, pausing as needed."""
        final_string = self._calculate_iterated_text(text, iterations)

        self.sonos_manager.snapshot_all()
        self.sonos_manager.set_all_volume()
        master_sonos_player = self.sonos_manager.group()
        master_sonos_player.play_file(OPENER_FILE_URL)

        if self.living_room_tv.current_activity_id:
            self.living_room_tv.pause()

        self.log("Speaking over TTS: {0}".format(final_string))

        self.run_in(
            self._speak_cb,
            3.25,
            master_sonos_player=master_sonos_player,
            text="Good {0}. {1}".format(
                relative_time_of_day(self), final_string
            ),
        )

        self._last_spoken_text = text
