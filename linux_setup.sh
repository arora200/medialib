#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
REPO_URL="https://github.com/your-username/medialib.git" # !!! IMPORTANT: Replace with your actual repository URL !!!
PROJECT_DIR="/var/www/medialib"
VENV_DIR="${PROJECT_DIR}/venv"
GUNICORN_PORT=5000
FLASK_APP_MODULE="app:app" # Assuming your Flask app instance is named 'app' in 'app.py'
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin" # !!! IMPORTANT: Change this to a strong, secure password !!!

# --- 1. Update System ---
echo "Updating system packages..."
sudo apt update
sudo apt upgrade -y
echo "System update complete."

# --- 2. Install Dependencies ---
echo "Installing necessary dependencies (Python3, pip, git, nginx, ffmpeg)..."
sudo apt install -y python3 python3-pip git nginx ffmpeg
echo "Dependencies installation complete."

# --- 3. Clone Repository ---
echo "Cloning Medialib repository from ${REPO_URL}..."
if [ -d "${PROJECT_DIR}" ]; then
    echo "Project directory already exists. Pulling latest changes."
    git -C "${PROJECT_DIR}" pull
else
    sudo mkdir -p "${PROJECT_DIR}"
    sudo chown "$USER":"$USER" "${PROJECT_DIR}" # Give ownership to current user for cloning
    git clone "${REPO_URL}" "${PROJECT_DIR}"
fi
echo "Repository cloning complete."

# --- 4. Create Virtual Environment ---
echo "Creating Python virtual environment..."
python3 -m venv "${VENV_DIR}"
echo "Virtual environment created."

# --- 5. Install Python Requirements ---
echo "Installing Python requirements..."
source "${VENV_DIR}/bin/activate"
pip install -r "${PROJECT_DIR}/requirements.txt"
pip install gunicorn # Install gunicorn in the virtual environment
deactivate
echo "Python requirements installed."

# --- 6. Database Initialization ---
echo "Initializing the database and creating admin user..."
# Run init_db in the virtual environment
source "${VENV_DIR}/bin/activate"
# Set environment variables for admin user during db init
ADMIN_USERNAME="${ADMIN_USERNAME}" ADMIN_PASSWORD="${ADMIN_PASSWORD}" python "${PROJECT_DIR}/app.py" init_db
deactivate
echo "Database initialization complete."

# --- 7. Configure Gunicorn Systemd Service ---
echo "Configuring Gunicorn systemd service..."
SERVICE_FILE="/etc/systemd/system/medialib.service"

sudo bash -c "cat > ${SERVICE_FILE}" <<EOF
[Unit]
Description=Gunicorn instance to serve medialib
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin"
Environment="ADMIN_USERNAME=${ADMIN_USERNAME}"
Environment="ADMIN_PASSWORD=${ADMIN_PASSWORD}"
ExecStart=${VENV_DIR}/bin/gunicorn --workers 3 --bind unix:${PROJECT_DIR}/medialib.sock -m 007 ${FLASK_APP_MODULE}
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl start medialib
sudo systemctl enable medialib
echo "Gunicorn service configured and started."

# --- 8. Configure Nginx ---
echo "Configuring Nginx reverse proxy..."
NGINX_CONF_FILE="/etc/nginx/sites-available/medialib"

sudo bash -c "cat > ${NGINX_CONF_FILE}" <<EOF
server {
    listen 80;
    server_name _; # Replace with your domain name or IP address

    location / {
        include proxy_params;
        proxy_pass http://unix:${PROJECT_DIR}/medialib.sock;
    }
}
EOF

sudo ln -sf "${NGINX_CONF_FILE}" "/etc/nginx/sites-enabled/"
sudo rm -f "/etc/nginx/sites-enabled/default" # Remove default Nginx config
sudo nginx -t # Test Nginx configuration
sudo systemctl restart nginx
echo "Nginx configured and restarted."

# --- 9. Firewall Configuration ---
echo "Configuring firewall (UFW)..."
sudo ufw allow 'Nginx HTTP'
sudo ufw enable -y # Enable UFW if not already enabled
echo "Firewall configured."

echo "Medialib setup complete! Access your application at http://your_vm_ip_address"
echo "Remember to replace 'your_vm_ip_address' with your DigitalOcean VM's actual IP address or domain name."
echo "Also, remember to change the ADMIN_PASSWORD in the script and in your database for security."
