#!/bin/bash

# Deployment Script für Todo App

# Variablen
APP_DIR="/home/ubuntu/todo-app"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/todo-app"

# Log-Verzeichnis erstellen
sudo mkdir -p $LOG_DIR
sudo chown ubuntu:ubuntu $LOG_DIR

# App-Verzeichnis erstellen
mkdir -p $APP_DIR
cd $APP_DIR

# Virtual Environment erstellen
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Supervisor-Konfiguration kopieren
sudo cp todo-app.conf /etc/supervisor/conf.d/

# Supervisor neu laden
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start todo-app

echo "Deployment abgeschlossen!"
