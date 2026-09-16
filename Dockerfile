FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY backend/requirements-runtime.lock.txt /app/requirements-runtime.lock.txt
RUN pip install --no-cache-dir -r requirements-runtime.lock.txt && useradd --create-home --uid 10001 predictor
COPY --chown=predictor:predictor backend /app
RUN mkdir -p /app/data/stryktipset && chown -R predictor:predictor /app/data
USER predictor
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4)" || exit 1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
