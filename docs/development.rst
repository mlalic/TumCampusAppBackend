Development Server
==================

In order to provide a uniform development environment for all developers,
a [Vagrant](http://vagrantup.com) configuration is included which makes
it very simple to start an isolated VM with all project dependencies
pre-installed.

Installation
------------

In order to use the Vagrant machine, only a few simple steps are required
to set up the dependencies on your host machine. The Vagrant box can be
used on all major platforms and is based on an Ubuntu 13.04. base image.

Follow these steps to set up your host:

1. `Install Vagrant <https://docs.vagrantup.com/v2/installation/>`_ for your
   operating system
2. `Install VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ for your
   operating system
3. Download the base Vagrant box (one time download) by::

       vagrant box add chef/ubuntu-13.04


Using the Vagrant Box
---------------------

In order to use the Vagrant box, there are only two required steps:

1. Boot up the VM by issuing a ``vagrant up`` command from the root of the
   project's repository on your host system (the directory containing the
   ``Vagrantfile`` file). Do note that the first time this command is used
   it may take slightly longer than on subsequent invocations due to the
   fact that the VM needs to be provisioned (i.e. all dependencies
   downloaded and installed).
2. SSH into the Vagrant box by issuing a ``vagrant ssh`` command from the
   root of the project's repository on your host system.

At this point, you are provided with a full command-line interface to a
running Ubuntu VM.

The VM is set up in such a way that upon starting the bash session, the
only thing necessary to start the development server is::

    cd tca
    ./run_dev_server.sh

The development server will now be accessible from the host machine at
the URL http://localhost:8888 (port forwarding from the VM's port 8000
to the host's 8888 is provided by the Vagrant configuration).

Any changes to the project files done from either the host file
system or the VM filesystem will be mirrored in the other one. This is
due to the fact that the Vagrant box mounts the host's repository
root directory at ``/vagrant``. The provisioning scripts provides a
convenience symlink to the ``/vagrant/tca/`` directory in the default
user's home directory to make the process of starting a new Development
server as painless as possible for developers who aren't interested in
knowing the internals behind the Vagrant box's operation.

Therefore, a common workflow when developing for the TCA backend would
be to start up the Vagrant box and the development server inside it.
After that, editing the source files should be done on the developer's
host machine directly. The Vagrant VM environment exists to shield the
developer's host machine from installing (possibly conflicting)
dependencies of the project.
