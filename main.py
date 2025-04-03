import os
import pathlib
import shutil
import subprocess
import threading
import time
from datetime import (
    datetime,
)

from bottle import (
    route,
    run,
    template,
)

last_update_success = True
last_update_text = None
last_update_ts = None

@route('/')
def index():
    return template(
        "index",
        last_update_success=last_update_success,
        last_update_text=last_update_text,
        last_update_ts=last_update_ts,
    )

def update_server():
    global last_update_success
    global last_update_text
    global last_update_ts
    last_update_success = False
    last_update_text = "Updating...\n"
    last_update_ts = datetime.now()

    last_update_text += "Load docker config\n"
    input_docker_config = workdir / "docker_config.json"

    docker_dir = pathlib.Path.home() / ".docker"
    docker_dir.mkdir(exist_ok=True)
    docker_config = docker_dir / "config.json"

    shutil.copy(str(input_docker_config), str(docker_config))


    process = subprocess.run(
        [ "/usr/bin/docker-compose", "--file", "horse.yml", "pull" ],
        cwd = str(repodir.resolve()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    last_update_text += process.stdout.decode()
    if process.returncode != 0:
        last_update_success = False
        last_update_text += "Failed!\n"
        return

    process = subprocess.run(
        [ "/usr/bin/docker-compose", "--file", "horse.yml", "up", "--detach", "--remove-orphans" ],
        cwd = str(repodir.resolve()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    last_update_text += process.stdout.decode()
    if process.returncode != 0:
        last_update_success = False
        last_update_text += "Failed!\n"
        return

    process = subprocess.run(
        [ "git", "tag", "--force", "deployed" ],
        cwd = str(repodir.resolve()),
    )
    if process.returncode != 0:
        raise Exception("Failed to move tag")

    last_update_text += "Updated!\n"
    last_update_success = True

def fetch_new_versions(git_url, repodir, keyfile):
    # Do some startup activities
    if not repodir.exists():
        retcode = subprocess.call(
            [
                "git", "clone",
                "--branch", "target",
                "--depth", "1",
                git_url,
                str(repodir.resolve())
            ],
            env = {"GIT_SSH_COMMAND": "ssh -i " + str(keyfile.resolve()) + " -o IdentitiesOnly=yes"},
        )
        if retcode != 0:
            raise Exception("Git clone failed")

        if not repodir.exists():
            raise Exception("Git clone failed")

    while True:
        master_hash = None

        retcode = subprocess.call(
            [
                "git", "fetch", "origin",
                "--depth", "1",
                "+refs/tags/target:refs/tags/target",
            ],
            env = {"GIT_SSH_COMMAND": "ssh -i " + str(keyfile.resolve()) + " -o IdentitiesOnly=yes"},
            cwd = str(repodir.resolve())
        )
        if retcode != 0:
            raise Exception("Git fetch failed")

        process = subprocess.run(
            [ "git", "show-ref", "--hash", "refs/tags/target" ],
            cwd = str(repodir.resolve()),
            stdout=subprocess.PIPE
        )
        if process.returncode == 0:
            # A SHA-1 hash, with a newline
            assert(len(process.stdout) == 41)
            master_hash = process.stdout[:-1]
        else:
            raise Exception("Failed to resolve target version")

        assert(master_hash is not None)

        needs_update = None

        process = subprocess.run(
            [ "git", "show-ref", "--exists", "refs/tags/deployed" ],
            cwd = str(repodir.resolve()),
        )
        if process.returncode == 2:
            print("Could not find tag, assuming we need to deploy")
            needs_update = True
        elif process.returncode == 0:
            process = subprocess.run(
                [ "git", "show-ref", "--hash", "refs/tags/deployed" ],
                cwd = str(repodir.resolve()),
                stdout=subprocess.PIPE,
            )
            if process.returncode == 0:
                # SHA-1 with a newline
                assert(len(process.stdout) == 41)
                hash = process.stdout[:-1]
                needs_update = hash != master_hash
            else:
                raise Exception("Failed to resolve current version")
        else:
            raise Exception("Failed to resolve current version")

        assert(needs_update is not None)

        if needs_update:
            print("Updating...")
            retcode = subprocess.call(
                [
                    "git", "switch", "--detach", "refs/tags/target",
                ],
                cwd = str(repodir.resolve())
            )
            if retcode != 0:
                raise Exception("Git switch failed")

            update_server()

        # Sleep until next attempt
        end = time.time() + 10 * 60
        while(time.time() < end):
            time.sleep(end - time.time())

if __name__ == '__main__':

    workdir = pathlib.Path(os.environ["WORKDIR"])

    repodir = workdir / "repo"
    keyfile = workdir / "deploymentKey"
    git_url = (workdir / "giturl").read_text().strip("\n")

    thread = threading.Thread(target = fetch_new_versions, args=(git_url, repodir, keyfile))
    thread.start()

    run(host='0.0.0.0', port=8080)
    # thread.join()
