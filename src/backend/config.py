import os
import secrets

PROJECT_NAME = "Car maintenance app"
FRONTEND_HOST = "http://localhost:2662"
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
BACKEND_RELOAD = os.environ.get("BACKEND_RELOAD", "false").lower() == "true"
