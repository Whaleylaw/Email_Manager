FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Create a startup script to run both continuous_sync.py and process_emails.py with logging
RUN echo '#!/bin/bash\n\
echo "Starting continuous_sync.py..."\n\
python continuous_sync.py > /app/logs/continuous_sync.log 2>&1 &\n\
echo "Starting process_emails.py..."\n\
python process_emails.py > /app/logs/process_emails.log 2>&1 &\n\
echo "Both processes started. Waiting..."\n\
wait' > /app/start.sh && chmod +x /app/start.sh

# Run both scripts
CMD ["/app/start.sh"]
