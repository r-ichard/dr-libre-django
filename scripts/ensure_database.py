"""Make sure a PostgreSQL server answers at DB_HOST:DB_PORT; start the local one if not."""

import os
import shutil
import socket
import subprocess
import sys
import time

START_TIMEOUT_SECONDS = 30
LOCAL_HOSTS = ("localhost", "127.0.0.1")
CREATE_ROLE_AND_DATABASE = (
    "SELECT format('CREATE ROLE %I LOGIN CREATEDB PASSWORD %L', :'role', :'password')\n"
    "WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'role')\\gexec\n"
    "SELECT format('CREATE DATABASE %I OWNER %I', :'database', :'role')\n"
    "WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'database')\\gexec\n"
)


def main() -> int:
    host = os.environ["DB_HOST"]
    port = int(os.environ["DB_PORT"])
    local_and_root = host in LOCAL_HOSTS and os.geteuid() == 0 and shutil.which("apt-get")

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
    subprocess.run(["/usr/bin/pg_ctlcluster", "15", "main", "start"], check=True)
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while not answers(host, port):
        if time.monotonic() > deadline:
            raise SystemExit(f"PostgreSQL did not answer at {host}:{port} in time")
        time.sleep(0.5)


def create_role_and_database() -> None:
    role, database = os.environ["DB_USER"], os.environ["DB_NAME"]
    password = os.environ["DB_PASSWORD"]
    # Values go in as psql variables on stdin, never on a command line or in a log.
    statements = (
        f"\\set role '{role}'\n\\set database '{database}'\n\\set password '{password}'\n"
        + CREATE_ROLE_AND_DATABASE
    )
    subprocess.run(
        ["/usr/bin/su", "postgres", "-c", "psql -v ON_ERROR_STOP=1 -q"],
        input=statements,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    sys.exit(main())
