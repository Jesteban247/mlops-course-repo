# Keep these settings consistent with the pipeline walkthrough notebook.
import os
from urllib.parse import quote_plus

def database_url():
    user = quote_plus(os.environ['DIABETES_DB_USER'])
    pwd = quote_plus(os.environ['DIABETES_DB_PASSWORD'])
    host = os.getenv('DIABETES_DB_HOST', 'diabetes-postgres.mlops-project.svc.cluster.local')
    db = quote_plus(os.getenv('DIABETES_DB_NAME', 'diabetes'))
    return f'postgresql+psycopg2://{user}:{pwd}@{host}:5432/{db}'

def s3_client():
    import boto3
    return boto3.client('s3', endpoint_url=os.getenv('S3_ENDPOINT_URL','http://minio.mlops-project.svc.cluster.local:9000'), region_name='us-east-1', aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'])
