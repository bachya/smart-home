"""Define a Python script to insert log entries into the HASS log."""
log_level = data["level"]
message = data["message"]

if log_level == "ERROR":
    logger.error(message)
elif log_level == "WARNING":
    logger.warning(message)
else:
    logger.info(message)
