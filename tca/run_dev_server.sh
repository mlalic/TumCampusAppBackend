#!/bin/bash
# Runs the Django development server
# Binds it to port 8000 of all interfaces
# This means that the server becomes accessible from the host machine
# on port 8888, since the Vagrant box's port 8000 is forwarded
echo "Access the server from your host at: http://127.0.0.1:8888"
./manage.py runserver 0.0.0.0:8000
