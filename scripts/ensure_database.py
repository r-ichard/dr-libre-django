"""Make sure a PostgreSQL server answers at DB_HOST:DB_PORT; start the local one if not."""

import os
import shutil
import socket
import subprocess
import sys
import time

START_TIMEOUT_SECONDS = 30
LOCAL_HOSTS = ("localhost", "127.0.0.1")
CLUSTER_VERSION = "15"
CLUSTER_NAME = "main"
FORBIDDEN_VALUE_CHARACTERS = ("'", '"', "\\", "\n", "\r")
CREATE_ROLE_AND_DATABASE = (
    "SELECT format('CREATE ROLE %I LOGIN CREATEDB PASSWORD %L', :'role', :'password')\n"
    "WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'role')\\gexec\n"
    "SELECT format('CREATE DATABASE %I OWNER %I', :'database', :'role')\n"
    "WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'database')\\gexec\n"
)


def main() -> int:
    host = require_environment("DB_HOST")
    port = int(require_environment("DB_PORT"))
    local_and_root = host in LOCAL_HOSTS and os.geteuid() == 0 and bool(shutil.which("apt-get"))

    if not answers(host, port):
        if not local_and_root:
            print(f"No PostgreSQL at {host}:{port} and cannot start one here", file=sys.stderr)
            return 1
        start_local_server(host, port)
    if local_and_root:
        create_role_and_database()
    return 0


def answers(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def start_local_server(host: str, port: int) -> None:
    if not shutil.which("pg_ctlcluster"):
        subprocess.run(["/usr/bin/apt-get", "update"], check=True)
        subprocess.run(["/usr/bin/apt-get", "install", "-y", "postgresql"], check=True)
    cluster = ["/usr/bin/pg_ctlcluster", CLUSTER_VERSION, CLUSTER_NAME, "start"]
    subprocess.run(cluster, check=True)  # noqa: S603
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while not answers(host, port):
        if time.monotonic() > deadline:
            raise SystemExit(f"PostgreSQL did not answer at {host}:{port} in time")
        time.sleep(0.5)


def require_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise SystemExit(f"Missing required environment variable {name}")
    return value


def require_psql_safe(name: str) -> str:
    value = require_environment(name)
    if any(character in value for character in FORBIDDEN_VALUE_CHARACTERS):
        # Never echo the value: it can be the password.
        raise SystemExit(f"{name} must not contain quotes, backslashes or line breaks")
    return value


def build_statements() -> str:
    role = require_psql_safe("DB_USER")
    database = require_psql_safe("DB_NAME")
    password = require_psql_safe("DB_PASSWORD")
    return (
        f"\\set role '{role}'\n\\set database '{database}'\n\\set password '{password}'\n"
        + CREATE_ROLE_AND_DATABASE
    )


def create_role_and_database() -> None:
    # Values go in as psql variables on stdin, never on a command line or in a log.
    subprocess.run(
        ["/usr/bin/su", "postgres", "-c", "psql -v ON_ERROR_STOP=1 -q"],
        input=build_statements(),
        text=True,
        check=True,
    )


if __name__ == "__main__":
    sys.exit(main())
