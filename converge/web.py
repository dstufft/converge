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
import io
import json
import lzma
import os
import tarfile

from flask import Flask, abort, request

from libcloud.storage.base import Container
from libcloud.storage.types import Provider, ObjectDoesNotExistError
from libcloud.storage.providers import get_driver

from converge import marconi as queue
from converge.utils import chunks


app = Flask("converge")

# Pull in CONVERGE_* values from the environment
app.config.update({
    k[9:]: v
    for k, v in os.environ.items()
    if k.upper().startswith("CONVERGE_")
})


@app.route("/<revision_id>/", methods=["HEAD", "GET"])
@app.route("/<revision_id>/<path:path>", methods=["HEAD", "GET"])
def html(revision_id, path="index.html"):
    container = Container(
        app.config["BUCKET"],
        None,
        get_driver(Provider.CLOUDFILES)(
            app.config["RACKSPACE_USER"],
            app.config["RACKSPACE_APIKEY"],
            region=app.config["RACKSPACE_REGION"],
        ),
    )

    # See if the requested file exists
    try:
        obj = container.get_object(
            "html/{revision}/{path}".format(revision=revision_id, path=path)
        )
    except ObjectDoesNotExistError:
        abort(404)

    # Get the requested file
    data = b""
    for chunk in obj.as_stream():
        data += chunk

    return data, 200, {k.replace("_", "-"): v for k, v in obj.extra.items()}


@app.route("/revision/<revision_id>/<build_id>/", methods=["PUT"])
def build(revision_id, build_id):
    # Check our authentication
    if not request.headers.get("X-Auth-Token") == app.config["AUTH_TOKEN"]:
        abort(403)

    container = Container(
        app.config["BUCKET"],
        None,
        get_driver(Provider.CLOUDFILES)(
            app.config["RACKSPACE_USER"],
            app.config["RACKSPACE_APIKEY"],
            region=app.config["RACKSPACE_REGION"],
        ),
    )

    # Store the coverage data
    container.upload_object_via_stream(
        (
            bytes([c for c in chunk if c is not None])
            for chunk in chunks(
                lzma.compress(
                    json.dumps({
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "address": request.remote_addr,
                        "data": request.get_json()["coverage_data"],
                    }).encode("utf"),
                ),
                2048,
            )
        ),
        "data/{revision}/{build}.xz".format(
            revision=revision_id,
            build=build_id,
        ),
    )

    try:
        container.get_object(
            "files/{revision}.tar.xz".format(revision=revision_id)
        )
    except ObjectDoesNotExistError:
        # Generate a tarball of the source files
        tarxz = io.BytesIO()
        with tarfile.open(
                "{}.tar.xz".format(revision_id),
                "w:xz",
                fileobj=tarxz) as tarball:
            for filename, file_data in (
                    request.get_json()["source_files"].items()):
                # Encode our file_data using utf8 so we can store it
                file_data = file_data.encode("utf8")

                # Add the file to the tarball
                info = tarfile.TarInfo(name=filename)
                info.size = len(file_data)
                tarball.addfile(tarinfo=info, fileobj=io.BytesIO(file_data))

        # Store the files tarball
        container.upload_object_via_stream(
            (
                bytes([c for c in chunk if c is not None])
                for chunk in chunks(tarxz.getvalue(), 2048)
            ),
            "files/{revision}.tar.xz".format(revision=revision_id),
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
            json.dumps({"success": False}),
            503,
            {"Content-Type": "application/json"},
        )

    # Return Information
    return (
        json.dumps({"success": True}),
        200,
        {"Content-Type": "application/json"},
    )


if __name__ == "__main__":
    app.run(debug=True)
