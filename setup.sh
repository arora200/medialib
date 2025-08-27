#!/bin/bash

# Update package lists
sudo apt-get update

# Install Python 3, pip, and the venv module
sudo apt-get install -y python3 python3-pip python3-venv

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment and install dependencies
source venv/bin/activate
pip install -r requirements.txt

echo "Setup complete. A virtual environment has been created in the 'venv' directory."
echo "To activate the virtual environment in the future, run: source venv/bin/activate"
echo "Once activated, you can run the application using: python app.py"