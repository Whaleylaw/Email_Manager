FROM nginx:1.25-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy the custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/email-inbox.conf

# Create directories for SSL certificates if they don't exist
RUN mkdir -p /etc/nginx/certs

EXPOSE 80 443

# Start Nginx
CMD ["nginx", "-g", "daemon off;"] 