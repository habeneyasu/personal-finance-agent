"""
Database connection helper for PFIP Lambda functions.

Reads credentials from AWS Secrets Manager (DB_SECRET_ARN env var) or falls back
to individual env vars (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD) for local dev.
"""

import json
import os
from contextlib import contextmanager

import boto3
import psycopg2


def get_connection() -> psycopg2.extensions.connection:
    """
    Return a psycopg2 connection.

    Priority:
    1. DB_SECRET_ARN (or DB_SECRET_NAME) → fetch JSON from Secrets Manager
    2. Individual env vars DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
    """
    secret_id = os.environ.get("DB_SECRET_ARN") or os.environ.get("DB_SECRET_NAME")

    if secret_id:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_id)
        secret = json.loads(response["SecretString"])
        host = secret["host"]
        port = int(secret.get("port", 5432))
        dbname = secret["dbname"]
        user = secret["username"]
        password = secret["password"]
    else:
        host = os.environ["DB_HOST"]
        port = int(os.environ.get("DB_PORT", 5432))
        dbname = os.environ["DB_NAME"]
        user = os.environ["DB_USER"]
        password = os.environ["DB_PASSWORD"]

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
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
