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
import datetime
import json
import os

from flask import request
from flask.ext.api import FlaskAPI, status

from libcloud.storage.base import Container
from libcloud.storage.types import Provider
from libcloud.storage.providers import get_driver

from converge import marconi as queue


app = FlaskAPI("converge")

# Pull in CONVERGE_* values from the environment
app.config.update({
    k[9:]: v
    for k, v in os.environ.items()
    if k.upper().startswith("CONVERGE_")
})


@app.route("/revision/<revision_id>/<build_id>/", methods=["GET", "PUT"])
def build(revision_id, build_id):
    # Store the data in the object store
    storage = get_driver(Provider.CLOUDFILES)(
        app.config["RACKSPACE_USER"],
        app.config["RACKSPACE_APIKEY"],
        region=app.config["RACKSPACE_REGION"],
    )
    storage.upload_object_via_stream(
        iter(
            json.dumps({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "address": request.remote_addr,
                "data": request.data,
            })
        ),
        Container(app.config["BUCKET"], None, storage),
        "data/{revision}/{build}".format(revision=revision_id, build=build_id),
        extra={"content_type": "application/json"},
    )

    try:
        queue.push(
            app.config["RACKSPACE_USER"],
            app.config["RACKSPACE_APIKEY"],
            app.config["QUEUE"],
            {"event": "revision.process", "revision": revision_id},
            region=app.config["RACKSPACE_REGION"],
        )
    except queue.QueueException:
        return (
            {"success": False},
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {"Retry-After": 30},
        )

    # Return Information
    return {"success": True}


if __name__ == "__main__":
    app.run(debug=True)
