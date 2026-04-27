"""
Database connection helper for PFIP Lambda functions.

Connection resolution order:
1. DB_HOST + DB_NAME + DB_USER + DB_PASSWORD (and optional DB_PORT) — used in AWS
   Lambda so the function never calls Secrets Manager over the network (avoids VPC
   endpoint / NAT issues that surface as API Gateway 502s).
2. DB_SECRET_ARN or DB_SECRET_NAME — fetch JSON from Secrets Manager (bastion, laptop
   with network path to AWS, or legacy setups).
"""

import json
import os
from contextlib import contextmanager

import boto3
import psycopg2


def _connect_timeout_sec() -> int | None:
    """
    libpq connect_timeout (seconds). Unset or invalid defaults to 30 so laptops
    do not hang forever on private RDS. Set DB_CONNECT_TIMEOUT=0 to wait indefinitely.
    """
    raw = os.environ.get("DB_CONNECT_TIMEOUT", "30").strip()
    if not raw:
        return 30
    try:
        n = int(raw)
    except ValueError:
        return 30
    if n <= 0:
        return None
    return n


def _connect_kwargs(
    *,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
) -> dict:
    kw: dict = {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }
    t = _connect_timeout_sec()
    if t is not None:
        kw["connect_timeout"] = t
    return kw


def _env_direct_db() -> dict[str, str | int] | None:
    host = os.environ.get("DB_HOST")
    password = os.environ.get("DB_PASSWORD")
    dbname = os.environ.get("DB_NAME")
    user = os.environ.get("DB_USER")
    if not (host and password and dbname and user):
        return None
    return {
        "host": host,
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": dbname,
        "user": user,
        "password": password,
    }


def get_connection() -> psycopg2.extensions.connection:
    """
    Return a psycopg2 connection.

    Priority:
    1. DB_HOST, DB_NAME, DB_USER, DB_PASSWORD (optional DB_PORT) when all required values are set
    2. DB_SECRET_ARN or DB_SECRET_NAME → Secrets Manager JSON (host, port, dbname, username, password)
    """
    direct = _env_direct_db()
    if direct is not None:
        return psycopg2.connect(
            **_connect_kwargs(
                host=direct["host"],
                port=int(direct["port"]),
                dbname=direct["dbname"],
                user=direct["user"],
                password=direct["password"],
            )
        )

    secret_id = os.environ.get("DB_SECRET_ARN") or os.environ.get("DB_SECRET_NAME")
    if not secret_id:
        raise KeyError(
            "Set DB_HOST/DB_NAME/DB_USER/DB_PASSWORD or DB_SECRET_ARN (or DB_SECRET_NAME)"
        )

    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_id)
    secret = json.loads(response["SecretString"])
    host = secret["host"]
    port = int(secret.get("port", 5432))
    dbname = secret["dbname"]
    user = secret["username"]
    password = secret["password"]

    return psycopg2.connect(
        **_connect_kwargs(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
        )
    )


@contextmanager
def get_cursor(conn: psycopg2.extensions.connection):
    """
    Context manager that yields a cursor, commits on clean exit, rolls back on exception.
    """
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
