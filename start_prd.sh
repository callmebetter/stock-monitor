#!/bin/bash

# uv run will find gunicorn inside .venv and execute it
uv run gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
