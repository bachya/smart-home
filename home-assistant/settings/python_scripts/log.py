"""Define a Python script to insert log entries into the HASS log."""
LOG_LEVEL = data["level"]
MESSAGE = data["MESSAGE"]

if LOG_LEVEL == "ERROR":
    logger.error(MESSAGE)
elif LOG_LEVEL == "WARNING":
    logger.warning(MESSAGE)
else:
    logger.info(MESSAGE)
