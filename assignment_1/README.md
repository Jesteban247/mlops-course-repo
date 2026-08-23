# Assignment 1

## Data

```bash
curl -L --retry 3 -o data/penguins.csv https://cdn.jsdelivr.net/gh/mwaskom/seaborn-data@master/penguins.csv
```

## Conda

```bash
conda env list
conda create -n penguins python=3.14 -y
conda activate penguins
pip install -r requirements.txt
pip freeze > requirements.txt

conda deactivate
conda env remove --name penguins
```

## Python

```bash
python train.py
python inference.py
```

## API

```bash
uvicorn api:app --host 0.0.0.0 --port 8989
```

```text
http://localhost:8989/docs
```

## Docker

```bash
docker build -t penguin-api .
docker images
docker run --rm -p 8989:8989 penguin-api
docker ps -a

docker rmi IMAGE_ID
```
