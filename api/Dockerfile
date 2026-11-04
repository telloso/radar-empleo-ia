FROM python:3.12-slim

WORKDIR /app

# Dependencies first: this layer is reused from cache while only the code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# A server stays up and listens on the network: do not run it as root.
RUN useradd --no-create-home --shell /usr/sbin/nologin api
USER api

EXPOSE 8000

# 0.0.0.0 = listen on every interface of the container, so Docker can forward
# the port to it (127.0.0.1 would only accept connections from inside the container).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
