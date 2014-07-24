#!/bin/bash

# A script to provision a blank Ubuntu system with the project's
# system-level dependencies

# Deb packages
# Set up rabbitmq repo
rabbitmq='deb http://www.rabbitmq.com/debian/ testing main'
if grep "$rabbitmq" /etc/apt/sources.list >/dev/null; then
    echo "RabbitMQ repository already registered"
else
    echo "# RabbitMQ repository\n$rabbitmq" >>/etc/apt/sources.list
    wget http://www.rabbitmq.com/rabbitmq-signing-key-public.asc
    apt-key add rabbitmq-signing-key-public.asc
fi

apt-get update
apt-get -y install python-pip python-all-dev python-all-dbg rabbitmq-server supervisor git
apt-get -y install nginx
apt-get install -y postgresql postgresql-contrib libpq-dev
# In order to install MySQL (and the required dependency for building the
# Python connector), uncomment the following line
# apt-get -y install mysql-server libmysqlclient-dev

# Python packages
pip install virtualenv virtualenvwrapper
echo 'source `which virtualenvwrapper.sh`' >>~/.bashrc
