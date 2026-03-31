FROM python:3.11-slim

WORKDIR /app

COPY dashboard/ ./dashboard/

RUN pip install --no-cache-dir streamlit==1.35.0 requests==2.32.2

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
