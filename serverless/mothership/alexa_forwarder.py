"""Define serverless functions to work with AppDaemon."""
# -*- coding: utf-8 -*-
import os
import json
import logging
import urllib3

_DEBUG = bool(os.environ.get("DEBUG"))

_LOGGER = logging.getLogger("AppDaemon-Intents")
_LOGGER.setLevel(logging.DEBUG if _DEBUG else logging.INFO)


def forward_invocation_handler(event, context):  # pylint: disable=unused-argument
    """Handle incoming Alexa directive."""
    _LOGGER.debug("Event: %s", event)

    base_url = os.environ.get("APPDAEMON_BASE_URL")
    assert base_url is not None, "Please set APPDAEMON_BASE_URL environment variable"

    http = urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED", timeout=urllib3.Timeout(connect=2.0, read=10.0)
    )

    response = http.request(
        "POST",
        "{}/api/appdaemon/alexa?api_password={}".format(
            base_url, os.environ.get("APPDAEMON_API_PASSWORD")
        ),
        body=json.dumps(event).encode("utf-8"),
    )
    if response.status >= 400:
        return {
            "event": {
                "payload": {
                    "type": "INVALID_AUTHORIZATION_CREDENTIAL"
                    if response.status in (401, 403)
                    else "INTERNAL_ERROR",
                    "message": response.data.decode("utf-8"),
                }
            }
        }
    return json.loads(response.data.decode("utf-8"))
