FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx redis 2>/dev/null
COPY spoke_base.py .
ARG SPOKE_ID
ENV SPOKE_ID=${SPOKE_ID}
EXPOSE 8080
CMD ["python", "spoke_base.py"]
