"""Define a Python script to insert log entries into the HASS log.

Produces a service like this:

service: python_script.log
data:
  level: INFO
  message: This is an info-level message
"""


def main():
    """Run the script."""
    log_level = data["level"]
    message = data["message"]

    if log_level == "ERROR":
        logger.error(message)
    elif log_level == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)


main()
