# Copyright 2014 Alex Stapleton
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

import argparse
import json
import os
import pickle
import requests
import sys


def main(argv):
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("revision", help="e.g. git commit id")
    arg_parser.add_argument("job", help="e.g. the Travis-CI build id")
    arg_parser.add_argument("coverage", help="path to coverage file")
    args = arg_parser.parse_args(argv[1:])

    config = {
        k[9:]: v
        for k, v in os.environ.items()
        if k.upper().startswith("CONVERGE_")
    }

    cover_data = pickle.load(open(args.coverage))
    cover_filenames = cover_data['arcs'].keys() + cover_data['lines'].keys()

    source_files = {
        name: open(name).read()
        for name in cover_filenames
    }

    requests.put(
        config['URL'].format(args.revision, args.job),
        headers={
            "Content-Type": "application/json",
            "X-Auth-Token": config['AUTH_TOKEN']
        },
        data=json.dumps({
            "pr": None,
            "branch": None,
            "coverage_data": cover_data,
            "source_files": source_files
        }),
    )


if __name__ == "__main__":
    main(sys.argv)
