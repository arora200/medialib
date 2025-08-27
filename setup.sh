#!/bin/bash

# Update package lists
sudo apt-get update

# Install Python 3 and pip
sudo apt-get install -y python3 python3-pip

# Install project dependencies
pip3 install -r requirements.txt

echo "Setup complete. You can now run the application using: python3 app.py"
