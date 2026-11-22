import os

from fastapi import FastAPI

app = FastAPI()


@app.get('/')
def root():
    return {'message': 'Hello from Project 3', 'pod': os.environ.get('HOSTNAME')}
