"""Send SMS notifications through Infobip."""

import http.client
import json
import os


def send_sms(message):
    required = ["INFOBIP_API_KEY", "INFOBIP_TO", "INFOBIP_SENDER"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing Infobip environment variables: {', '.join(missing)}")

    host = os.getenv("INFOBIP_BASE_URL", "55z85g.api.infobip.com")
    payload = json.dumps(
        {
            "messages": [
                {
                    "destinations": [{"to": os.environ["INFOBIP_TO"]}],
                    "sender": os.environ["INFOBIP_SENDER"],
                    "content": {"text": message},
                }
            ]
        }
    )
    headers = {
        "Authorization": f"App {os.environ['INFOBIP_API_KEY']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    connection = http.client.HTTPSConnection(host, timeout=30)
    try:
        connection.request("POST", "/sms/3/messages", payload, headers)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
    finally:
        connection.close()

    print(f"Infobip HTTP status: {response.status} {response.reason}")
    print(body)
    if not 200 <= response.status < 300:
        raise RuntimeError(f"Infobip returned HTTP {response.status}: {body}")
    return body
