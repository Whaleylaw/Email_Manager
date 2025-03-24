# Email Manager System

This system provides an automated email triage and management solution with a Streamlit-based inbox for easier email management.

## Components

1. **Email Triage**: Automatically syncs emails, analyzes them, and stores their embeddings in Supabase
2. **Streamlit Inbox**: Web interface for viewing and managing emails with AI integration

## Deployment Instructions

### Prerequisites

- Docker and Docker Compose installed
- Supabase account with a project set up
- OpenAI API key
- Email account with IMAP access

### Setup

1. **Configure Environment Variables**:
   Edit the `.env` file in the root directory and update:
   - Supabase URL and key
   - OpenAI API key
   - Email credentials

2. **Build and Start Containers**:
   ```bash
   docker-compose up -d
   ```

3. **Access the Streamlit Inbox**:
   Open a web browser and navigate to:
   ```
   http://localhost:8501
   ```

4. **View Logs**:
   ```bash
   docker-compose logs -f
   ```

### Remote Access Setup

To access the Streamlit inbox remotely, consider:

1. Setting up a reverse proxy (Nginx/Traefik)
2. Using a VPN
3. Deploying to a cloud provider

## Maintenance

- Monitor the logs directory for any issues
- Restart containers if needed:
  ```bash
  docker-compose restart
  ```

## Additional Configuration

For more advanced configurations, see the documentation in each component's directory.
