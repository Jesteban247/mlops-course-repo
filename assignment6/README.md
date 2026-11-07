```bash
python -m pip install -r requirements.txt
python -m pytest -v --cov=app --cov-report=term-missing
docker build -t ml-preprocessing-api .
docker run --rm -p 8000:8000 --name ml-preprocessing-api ml-preprocessing-api
curl http://localhost:8000/health
curl -X POST http://localhost:8000/preprocess -H "Content-Type: application/json" -d '{"text":"This is a SIMPLE example!","stopwords":["a","an","the","is"]}'
docker inspect --format='{{.State.Health.Status}}' ml-preprocessing-api
docker rm -f ml-preprocessing-api
docker rmi ml-preprocessing-api
```
