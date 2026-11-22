"""Drop the database named by DB_NAME; used to clean up a throwaway validation database."""

import os

import psycopg
from psycopg import sql


def main() -> None:
    with psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname="postgres",
        autocommit=True,
    ) as connection:
        statement = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)")
        connection.execute(statement.format(sql.Identifier(os.environ["DB_NAME"])))


if __name__ == "__main__":
    main()
