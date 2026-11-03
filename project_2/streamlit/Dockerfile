FROM python:3.12-slim
WORKDIR /app
COPY streamlit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY streamlit/app.py streamlit/examples.json ./
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
