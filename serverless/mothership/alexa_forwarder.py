"""Define serverless functions to work with AppDaemon."""
import requests

APPDAEMON_API_PASSWORD = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
APPDAEMON_URL = "https://appdaemon.myserver.com/api/appdaemon/alexa"


def forward_invocation_handler(event, context):  # pylint: disable=unused-argument
    """Forward an Alexa intent invocation to AppDaemon."""
    resp = requests.post(
        APPDAEMON_URL, params={"api_password": APPDAEMON_API_PASSWORD}, json=event
    )
    return resp.json()
