# gpt_sandbox Yoga Reservation App

This repository contains a minimal FastAPI application that lets users sign up, log in and reserve yoga sessions. An admin account (email: `admin@example.com` / password: `admin`) is created automatically when the app starts.

## Running locally

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Start the development server:
   ```bash
   python main.py  # listens on http://localhost:8000
   ```
   The SQLite database `yoga.db` will be created in the project directory on first run.

## Deployment

For a simple deployment you can run `uvicorn` directly or use Docker.

### Using Uvicorn/Gunicorn

Run the app with Uvicorn in production mode (for example behind an nginx proxy):
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker

Build and run a Docker container:
```bash
docker build -t yoga-app .
docker run -p 8000:8000 yoga-app
```

A sample `Dockerfile` is provided below:
```Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```
