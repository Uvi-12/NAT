FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir dapr-ext-workflow==1.18.3 flask==3.0.3
COPY app.py /app/app.py
CMD ["python", "app.py"]
