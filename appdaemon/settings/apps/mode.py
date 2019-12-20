"""Define a mode."""
from const import EVENT_MODE_CHANGE
from core import Base


class Mode(Base):
    """Define a mode."""

    def on_disable(self) -> None:
        """Deactivate the mode when its input boolean is toggled off."""
        self.log("Deactivating mode: %s", self.name)
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="off")

    def on_enable(self) -> None:
        """Deactivate the mode when its input boolean is toggled on."""
        self.log("Activating mode: %s", self.name)
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="on")
