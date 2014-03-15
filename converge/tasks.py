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
import io
import json
import lzma
import os.path
import tarfile
import tempfile

from coverage import CoverageData, coverage
from libcloud.storage.base import Container
from libcloud.storage.types import Provider
from libcloud.storage.providers import get_driver

from converge.utils import make_real_path


def process_revision(config, revision):
    storage = get_driver(Provider.CLOUDFILES)(
        config["RACKSPACE_USER"],
        config["RACKSPACE_APIKEY"],
        region=config["RACKSPACE_REGION"],
    )

    # Get our data files
    data = []
    for obj in storage.iterate_container_objects(
            Container(config["BUCKET"], None, storage),
            ex_prefix="data/{}".format(revision)):
        obj_data = b""
        for chunk in obj.as_stream():
            obj_data += chunk
        data.append(json.loads(lzma.decompress(obj_data).decode("utf8")))

    # Get our source files
    obj = storage.get_object(
        config["BUCKET"],
        "files/{revision}.tar.xz".format(revision=revision),
    )
    tarball = b""
    for chunk in obj.as_stream():
        tarball += chunk

    # Write out our source files into a temporary location
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract the tarball to our temporary directory
        with tarfile.open(fileobj=io.BytesIO(tarball), mode="r") as tb:
            tb.extractall(tmpdir)

        cdata = CoverageData()

        for datum in data:
            cdata.add_line_data({
                make_real_path(tmpdir, k): dict.fromkeys(v)
                for k, v in datum["data"].get("lines", {}).items()
            })
            cdata.add_arc_data({
                make_real_path(tmpdir, k): dict.fromkeys(map(tuple, v))
                for k, v in datum["data"].get("arcs", {}).items()
            })

        current_directory = os.path.abspath(".")
        try:
            os.chdir(tmpdir)

            cov = coverage()
            cov.data = cdata

            with tempfile.TemporaryDirectory() as htmldir:
                # Generate a HTML report for our data
                cov.html_report(directory=htmldir)

                # Upload the HTML report
                for dirname, dirnames, filenames in os.walk(htmldir):
                    for filename in filenames:
                        path = os.path.relpath(
                            os.path.join(dirname, filename),
                            htmldir,
                        )

                        storage.upload_object(
                            os.path.join(htmldir, path),
                            Container(config["BUCKET"], None, storage),
                            os.path.join("html", revision, path),
                        )
        finally:
            os.chdir(current_directory)
