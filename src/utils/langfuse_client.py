import os
import uuid
import time
import requests
from requests.auth import _basic_auth_str

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")


def new_trace_id():
    return str(uuid.uuid4())


def _headers():
    return {
        "Authorization": _basic_auth_str(
            LANGFUSE_PUBLIC_KEY,
            LANGFUSE_SECRET_KEY
        ),
        "Content-Type": "application/json"
    }


def create_trace(trace_id, name, input_data=None):
    payload = {
        "batch": [
            {
                "id": str(uuid.uuid4()),
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime()
                ),
                "type": "trace-create",
                "body": {
                    "id": trace_id,
                    "name": name,
                    "input": input_data
                }
            }
        ]
    }

    requests.post(
        f"{LANGFUSE_HOST}/api/public/ingestion",
        headers=_headers(),
        json=payload,
        timeout=10
    )


def create_observation(
    trace_id,
    name,
    input_data=None,
    output_data=None,
    metadata=None
):
    payload = {
        "batch": [
            {
                "id": str(uuid.uuid4()),
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime()
                ),
                "type": "observation-create",
                "body": {
                    "id": str(uuid.uuid4()),
                    "traceId": trace_id,
                    "name": name,
                    "type": "GENERATION",
                    "input": input_data,
                    "output": output_data,
                    "metadata": metadata or {}
                }
            }
        ]
    }

    requests.post(
        f"{LANGFUSE_HOST}/api/public/ingestion",
        headers=_headers(),
        json=payload,
        timeout=10
    )