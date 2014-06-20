#!/bin/bash

# A script to provision a brand new Vagrant box

# System-level dependencies

# Deb packages
# Set up rabbitmq repo
echo 'deb http://www.rabbitmq.com/debian/ testing main' >>/etc/apt/sources.list
wget http://www.rabbitmq.com/rabbitmq-signing-key-public.asc
apt-key add rabbitmq-signing-key-public.asc

apt-get update
apt-get -y install python-pip python-dev rabbitmq-server

# Python packages
pip install virtualenv virtualenvwrapper

# Update the .bashrc file to automatically load virtualenvwrapper for
# each bash session
echo 'source `which virtualenvwrapper.sh`' >>/home/vagrant/.bashrc
# Automatically start the session working on the tca-dev virtualenv
echo 'workon tca-dev' >>/home/vagrant/.bashrc

# Set up the TCA Backend project
ln -s /vagrant/tca /home/vagrant/tca

# Set up a dedicated virtualenv for the development of the TCA project
# This should be done under the default user, not root
su vagrant <<'EOF'
. `which virtualenvwrapper.sh`
mkvirtualenv tca-dev
pip install -r /home/vagrant/tca/requirements.txt
pip install -r /home/vagrant/tca/requirements-dev.txt
# Initial syncdb, just in case
cd ~/tca/ && ./manage.py syncdb --noinput
# Set up development settings for the Vagrant box
cd ~/tca/tca/settings/ && ln -s development.py local_settings.py
EOF
