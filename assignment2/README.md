# Assignment 2

Run all commands from the `assignment2` directory.

## Start from zero

```bash
docker compose build --no-cache
```

## Start the services

```bash
mkdir -p notebooks models data
docker compose up
```

Check the terminal for the JupyterLab and API links.

A bind mount connects a local folder to a folder inside the container, while a named volume is managed by Docker.
Both services use local mounts so notebooks, data, and trained models are accessible from the host system.

## Test the API

Health check:

```bash
curl http://localhost:8000/health
```

Prediction:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"model":"random_forest","features":[5.1,3.5,1.4,0.2]}'
```

List the available models:

```bash
curl http://localhost:8000/models
```

The `model` value must match the name of a `.pkl` file in the `models/`
directory, without the `.pkl` extension.

## Stop the services

```bash
docker compose down
```

## Demo

![API demo](files/Demo.gif)
