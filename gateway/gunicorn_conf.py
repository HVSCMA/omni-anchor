
import os

# Gunicorn configuration file for google_assistant_webhook.py

bind = "0.0.0.0:5001"  # Listen on all interfaces on port 5001

# The module and application object to run
# Assumes google_assistant_webhook.py contains an 'app' instance
wsgi_app = "gateway.google_assistant_webhook:app"

# Number of worker processes (usually 2xcores + 1, adjust as needed)
workers = os.cpu_count() * 2 + 1 if os.cpu_count() else 3

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
