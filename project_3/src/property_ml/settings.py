import os
from sqlalchemy import URL, create_engine


def engine():
    return create_engine(URL.create('postgresql+psycopg2', username=os.environ['APP_DB_USER'],
        password=os.environ['APP_DB_PASSWORD'], host=os.getenv('APP_DB_HOST', 'property-postgres'),
        database=os.environ['APP_DB_NAME'], port=int(os.getenv('APP_DB_PORT', '5432'))), pool_pre_ping=True)


GROUP = int(os.getenv('DATA_API_GROUP', '4'))
MODEL_NAME = os.getenv('MODEL_NAME', 'property-price')
