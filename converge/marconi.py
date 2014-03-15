# Copyright 2014 Donald Stufft
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import urllib.parse

import requests

CLIENT_ID = "20af609a-4a6f-45aa-a9b0-d7946274dc52"


class QueueException(Exception):
    pass


def _get_auth_token(user, key):
    # Get the auth token
    resp = requests.post(
        "https://identity.api.rackspacecloud.com/v2.0/tokens",
        data=json.dumps({
            "auth": {
                "RAX-KSKEY:apiKeyCredentials": {
                    "username": user,
                    "apiKey": key,
                }
            }
        }),
        headers={
            "Content-Type": "application/json",
        }
    )
    resp.raise_for_status()
    return resp.json()["access"]["token"]["id"]


def push(user, key, queue, message, ttl=1209600, retries=20, region="iad"):
    # Send message to queue
    for _ in range(retries):
        resp = requests.post(
            (
                "https://{}.queues.api.rackspacecloud.com/v1/queues/{}/"
                "messages".format(region, queue)
            ),
            data=json.dumps([{"ttl": ttl, "body": message}]),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Auth-Token": _get_auth_token(user, key),
                "Client-ID": CLIENT_ID,
            }
        )
        resp.raise_for_status()

        if not resp.json()["partial"]:
            return
    else:
        raise QueueException("Cannot Queue Message")


def claim(user, key, queue, ttl=300, grace=300, region="iad"):
    resp = requests.post(
        (
            "https://{}.queues.api.rackspacecloud.com/v1/queues/{}/"
            "claims".format(region, queue)
        ),
        data=json.dumps({"ttl": ttl, "grace": grace, "limit": 1}),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Auth-Token": _get_auth_token(user, key),
            "Client-ID": CLIENT_ID,
        }
    )
    resp.raise_for_status()

    # Check if we got any items returned
    if resp.status_code == 204:
        return

    # Insert the claim location into the data too
    data = resp.json()[0]
    data["claim"] = resp.headers["Location"]

    return data


def unclaim(user, key, queue, task, region="iad"):
    resp = requests.delete(
        urllib.parse.urljoin(
            "https://{}.queues.api.rackspacecloud.com/".format(region),
            task["claim"],
        ),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Auth-Token": _get_auth_token(user, key),
            "Client-ID": CLIENT_ID,
        }
    )
    resp.raise_for_status()


def delete(user, key, queue, task, region="iad"):
    resp = requests.delete(
        urllib.parse.urljoin(
            "https://{}.queues.api.rackspacecloud.com/".format(region),
            task["href"],
        ),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Auth-Token": _get_auth_token(user, key),
            "Client-ID": CLIENT_ID,
        }
    )
    resp.raise_for_status()
