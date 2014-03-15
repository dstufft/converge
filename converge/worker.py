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
import os
import sys
import time

from converge import marconi as queue
from converge import tasks


def main(args):
    # Get our configuration
    config = {
        k[9:]: v
        for k, v in os.environ.items()
        if k.upper().startswith("CONVERGE_")
    }

    task = None

    try:
        # Do Our Busy Loop
        while True:
            # grab a Task from the queue
            task = queue.claim(
                config["RACKSPACE_USER"],
                config["RACKSPACE_APIKEY"],
                config["QUEUE"],
                region=config["RACKSPACE_REGION"],
            )

            if task is not None:
                # Do Our Task
                if task["body"]["event"] == "revision.process":
                    tasks.process_revision(config, task["body"]["revision"])
                else:
                    raise ValueError(
                        "Unknown event '{}'".format(task["body"]["event"])
                    )

                # Delete the task now that it's been processed
                queue.delete(
                    config["RACKSPACE_USER"],
                    config["RACKSPACE_APIKEY"],
                    config["QUEUE"],
                    task,
                    region=config["RACKSPACE_REGION"],
                )

                task = None
            else:
                # If there were no tasks, wait for 5 seconds and try again
                time.sleep(5)
    except KeyboardInterrupt:
        print("Exiting converge.worker...")

        # Release any claims we have as we are shutting down
        if task is not None:
            queue.unclaim(
                config["RACKSPACE_USER"],
                config["RACKSPACE_APIKEY"],
                config["QUEUE"],
                task,
                region=config["RACKSPACE_REGION"],
            )

        return
    except:
        # Release any claims we have as we hit an error
        if task is not None:
            queue.unclaim(
                config["RACKSPACE_USER"],
                config["RACKSPACE_APIKEY"],
                config["QUEUE"],
                task,
                region=config["RACKSPACE_REGION"],
            )

        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
