"""Send one Infobip SMS using values from the project .env file."""

import http.client
import json
import os
from pathlib import Path


def load_project_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


def main():
    load_project_env()
    required = ["INFOBIP_API_KEY", "INFOBIP_TO", "INFOBIP_SENDER"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Missing .env values: {', '.join(missing)}")

    host = os.getenv("INFOBIP_BASE_URL", "55z85g.api.infobip.com")
    message = os.getenv(
        "INFOBIP_TEST_MESSAGE",
        "Prueba de SMS de Project 1: la conexión con Infobip funciona.",
    )
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
        print(f"Infobip HTTP status: {response.status} {response.reason}")
        print(body)
        if not 200 <= response.status < 300:
            raise SystemExit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
