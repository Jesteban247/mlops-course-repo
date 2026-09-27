"""PostgreSQL storage helpers used by Project 1 DAGs."""

import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import execute_values


TABLE_NAME = "cover_samples"
DATA_COLUMNS = [
    "elevation",
    "aspect",
    "slope",
    "horizontal_distance_to_hydrology",
    "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways",
    "hillshade_9am",
    "hillshade_noon",
    "hillshade_3pm",
    "horizontal_distance_to_fire_points",
    "wilderness_area",
    "soil_type",
    "cover_type",
]
TABLE_COLUMNS = ["group_number", "batch_number", *DATA_COLUMNS]
FEATURE_CONSTRAINT = "uq_cover_samples_group_batch_features"


def connect():
    return psycopg2.connect(
        host=os.getenv("PROJECT_DATA_DB_HOST", "project-data-storage"),
        port=int(os.getenv("PROJECT_DATA_DB_PORT", "5432")),
        dbname=os.getenv("PROJECT_DATA_DB_NAME", "cover_data"),
        user=os.getenv("PROJECT_DATA_DB_USER", "cover_user"),
        password=os.getenv("PROJECT_DATA_DB_PASSWORD", "cover_password"),
        connect_timeout=15,
    )


@contextmanager
def database_connection():
    connection = connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def create_table():
    feature_columns = ", ".join(f'"{name}"' for name in DATA_COLUMNS)
    ddl = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            group_number INTEGER NOT NULL CHECK (group_number BETWEEN 1 AND 10),
            batch_number INTEGER NOT NULL,
            {', '.join(f'"{name}" TEXT NOT NULL' for name in DATA_COLUMNS)},
            CONSTRAINT {FEATURE_CONSTRAINT} UNIQUE (group_number, batch_number, {feature_columns})
        )
    """
    with database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(ddl)
        cursor.execute(
            f"ALTER TABLE {TABLE_NAME} "
            "DROP CONSTRAINT IF EXISTS uq_cover_samples_group_features"
        )
        cursor.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{FEATURE_CONSTRAINT}'
                      AND conrelid = '{TABLE_NAME}'::regclass
                ) THEN
                    ALTER TABLE {TABLE_NAME}
                    ADD CONSTRAINT {FEATURE_CONSTRAINT}
                    UNIQUE (group_number, batch_number, {feature_columns});
                END IF;
            END $$;
            """
        )


def clear_table():
    with database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {TABLE_NAME}")


def insert_sample(group_number, batch_number, rows, max_new_rows=None):
    if not rows:
        return count_batch_rows(group_number, batch_number)

    columns = ", ".join(f'"{name}"' for name in TABLE_COLUMNS)
    input_columns = ", ".join(f'"{name}"' for name in TABLE_COLUMNS)
    feature_columns = ", ".join(f'"{name}"' for name in DATA_COLUMNS)
    same_features = " AND ".join(
        f'present."{name}" = incoming."{name}"' for name in DATA_COLUMNS
    )
    values = [
        (group_number, int(batch_number), *(str(value) for value in row))
        for row in rows
    ]
    with database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TEMP TABLE cover_samples_incoming "
            f"(LIKE {TABLE_NAME}) ON COMMIT DROP"
        )
        execute_values(
            cursor,
            f"INSERT INTO cover_samples_incoming ({input_columns}) VALUES %s",
            values,
            template="(" + ",".join(["%s"] * len(TABLE_COLUMNS)) + ")",
            page_size=1000,
        )
        cursor.execute(
            f"""
            INSERT INTO {TABLE_NAME} ({columns})
            SELECT {input_columns}
            FROM (
                SELECT DISTINCT ON (incoming.group_number, incoming.batch_number, {feature_columns}) incoming.*
                FROM cover_samples_incoming AS incoming
                WHERE NOT EXISTS (
                    SELECT 1 FROM {TABLE_NAME} AS present
                    WHERE present.group_number = incoming.group_number
                      AND present.batch_number = incoming.batch_number
                      AND {same_features}
                )
                ORDER BY incoming.group_number, incoming.batch_number,
                         {', '.join(f'incoming."{name}"' for name in DATA_COLUMNS)}
                LIMIT %s
            ) AS candidates
            ON CONFLICT ON CONSTRAINT {FEATURE_CONSTRAINT} DO NOTHING
            """,
            (int(max_new_rows) if max_new_rows is not None else len(values),),
        )
        cursor.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE group_number = %s AND batch_number = %s",
            (group_number, int(batch_number)),
        )
        return cursor.fetchone()[0]


def count_group_rows(group_number):
    with database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE group_number = %s",
            (group_number,),
        )
        return cursor.fetchone()[0]


def count_batch_rows(group_number, batch_number):
    with database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} "
            "WHERE group_number = %s AND batch_number = %s",
            (group_number, int(batch_number)),
        )
        return cursor.fetchone()[0]


def inspect_table(head_size=5):
    with database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = current_schema() AND table_name = %s
               ORDER BY ordinal_position""",
            (TABLE_NAME,),
        )
        columns = [row[0] for row in cursor.fetchall()]
        if not columns:
            return {"exists": False, "columns": [], "row_count": 0, "head": []}

        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        row_count = cursor.fetchone()[0]
        cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY group_number LIMIT %s", (head_size,))
        head = cursor.fetchall()
        return {"exists": True, "columns": columns, "row_count": row_count, "head": head}


__all__ = [
    "DATA_COLUMNS",
    "TABLE_COLUMNS",
    "TABLE_NAME",
    "clear_table",
    "connect",
    "count_group_rows",
    "count_batch_rows",
    "create_table",
    "insert_sample",
    "inspect_table",
]
