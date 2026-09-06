# Assignment 2

Ejecuta todos los comandos desde el directorio `assignment2`.

## Empezar desde cero

```bash
docker compose build --no-cache
```

## Levantar los servicios

```bash
mkdir -p notebooks models data
docker compose up
```

Revisa la terminal para ver los links de JupyterLab y de la API.

Un bind mount conecta una carpeta local con una carpeta dentro del contenedor, mientras que un volumen nombrado es administrado por Docker.
Ambos servicios usan montajes locales para que los notebooks, los datos y los modelos entrenados sean accesibles desde el sistema anfitrión (host).

## Entrenar y promover un modelo

Correr un notebook de entrenamiento (`03`, `04` o `05`) solo genera un **candidato**:
`models/<nombre>.pkl` más `models/<nombre>.metrics.json`. Esto no cambia lo que sirve la API.

Para que un candidato pase a producción, hay que revisarlo y promoverlo explícitamente con
`notebooks/06_promote_model.ipynb`. Ese notebook compara las métricas del candidato contra
lo que actualmente está registrado en `models/production/manifest.json` y, una vez que decides
que es el mejor modelo, lo copia a `models/production/<nombre>/<version>/model.pkl` y registra
la nueva versión en el manifest — la API siempre lee desde ahí. Un candidato más nuevo
nunca reemplaza producción por sí solo; alguien tiene que promoverlo.

## Probar la API

Chequeo de salud:

```bash
curl http://localhost:8000/health
```

Predicción:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"model":"random_forest","features":[5.1,3.5,1.4,0.2]}'
```

Respuesta esperada — incluye la versión del modelo que respondió:

```json
{"model":"random_forest","version":"v1","prediction":0,"class_name":"setosa"}
```

Listar los modelos actualmente en producción, con su versión activa y sus métricas:

```bash
curl http://localhost:8000/models
```

El valor de `model` debe coincidir con un nombre registrado en `models/production/manifest.json`
(promovido a través de `06_promote_model.ipynb`). Cada respuesta de predicción incluye la
`version` que respondió, así que quien consume la API siempre sabe qué versión del modelo obtuvo.

## Detener los servicios

```bash
docker compose down
```

## Demo

![API demo](files/Demo.gif)
