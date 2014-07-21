"""
The fabric deployment script for the TCA project.
"""
from fabric.api import *
from fabric.colors import *

import os
from io import BytesIO
from contextlib import contextmanager


env.conf = {
    'project_name': 'TumCampusAppBackend',
    'deployment_id': 'tca-dev',
    'deployment_dir': 'deployments/',
    'git': {
        'url': 'https://github.com/mlalic/TumCampusAppBackend.git',
    },
    'supervisord': {
        'conf.d': '/etc/supervisor/conf.d/',
    },
    'nginx': {
        'etc': '/etc/nginx/',
    },
    'virtualenv': 'tca-dev',
    'django_settings': {
        'TCA_DOMAIN_NAME': '"ec2-54-74-61-201.eu-west-1.compute.amazonaws.com"',
        'TCA_SCHEME': '"http"',
        'TCA_GCM_API_KEY': '"PUT_THE_ACTUAL_KEY_HERE!!!"',
        'ALLOWED_HOSTS': '[TCA_DOMAIN_NAME]',
        'STATIC_ROOT': '"/home/ubuntu/deployments/static"',
    },
}


@contextmanager
def virtualenv(venv):
    """
    A context manager which activates a Python virtualenv on the remote host
    and keeps it active until the context is exitted.

    Relies on the remote host having ``virtualenvwrapper`` installed.
    """
    if venv is not None:
        with prefix('source `which virtualenvwrapper.sh`'):
            with prefix('workon {venv}'.format(venv=venv)):
                yield
    else:
        yield


class Supervisor(object):
    """
    Provides a convenient interface to using supervisord.
    """
    def __init__(self, conf_dir):
        self.conf_dir = conf_dir

    def _serialize_to_ini(self, config_name, config):
        """Serializes the given config dict to a supervisord formatted ini file.
        The ``config_name`` is the name of the program to which the config
        relates.
        """
        HEADER_TEMPLATE = '[program:{config_name}]'
        config_string = '\n'.join(
                '{key}={value}'.format(key=key, value=value)
                for key, value in config.items())
        header = HEADER_TEMPLATE.format(config_name=config_name)
        program_stanza = '\n'.join((header, config_string))

        return program_stanza

    def _build_conf_file_path(self, conf_name):
        return os.path.join(
            self.conf_dir,
            conf_name + '.conf')

    def register_to_supervisor(self, conf_name, config):
        config_string = self._serialize_to_ini(conf_name, config)
        supervisord_config_file = self._build_conf_file_path(conf_name)

        put(BytesIO(config_string), supervisord_config_file, use_sudo=True)

    def reload(self):
        sudo('supervisorctl reload')

    def stop(self, service_name):
        sudo('supervisorctl stop {name}'.format(name=service_name))

    def start(self, service_name):
        sudo('supervisorctl start {name}'.format(name=service_name))


class Nginx(object):
    def __init__(self, nginx_etc):
        self.etc_dir = nginx_etc

    def _build_conf_file_path(self, site_name):
        return os.path.join(
            self.etc_dir,
            'sites-available',
            site_name)

    def add_site(self, site_name, site_settings, auto_enable=True):
        site_config_file = self._build_conf_file_path(site_name)
        put(BytesIO(site_settings), site_config_file, use_sudo=True)
        if auto_enable:
            self.enable_site(site_name)

    def enable_site(self, site_name):
        site_config_file = self._build_conf_file_path(site_name)
        with cd(os.path.join(self.etc_dir, 'sites-enabled')):
            sudo('ln -s {site}'.format(site=site_config_file))

    def disable_site(self, site_name):
        with cd(os.path.join(self.etc_dir, 'sites-enabled')):
            sudo('rm {site}'.format(site=site_name))

    def remove_site(self, site_name):
        site_config_file = self._build_conf_file_path(site_name)
        sudo('rm {file}'.format(file=site_config_file))

    def restart(self):
        sudo('service nginx restart')


def get_django_settings(settings_dict):
    """
    Converts a dict of settings values to a string suitable for inclusion
    in a Django settings file.
    """
    return '\n'.join((
        '{key} = {value}'.format(key=key, value=value)
        for key, value in settings_dict.items()
    ))


class Git(object):
    CLONE_CMD = 'git clone {repo_url} {dest_dir}'

    def _run_cmd(self, cmd, *args, **kwargs):
        with hide('output', 'running'):
            return run(cmd.format(*args, **kwargs))

    def clone(self, repo_url, dest_dir=None):
        if dest_dir is None:
            dest_dir = ''

        return self._run_cmd(
            self.CLONE_CMD,
            repo_url=repo_url,
            dest_dir=dest_dir)


git = Git()


class Pip(object):
    def requirements(self, requirements):
        return 'pip install -r {reqs}'.format(reqs=requirements)

    def package(self, package):
        pass


pip = Pip()


class DjangoProjectConfigurator(object):
    """
    A class providing convenience method for performing some Django
    project management operations on a remote host relying on Fabric.
    """
    def __init__(self, remote_project_dir, venv=None):
        """
        :param remote_project_dir: The path to the directry on the remote
            host containing the ``manage.py`` script.
        :param venv: The name of the virtualenv that the project runs in.
            If None, no virtualenv will be considered
        """
        self.remote_project_dir = remote_project_dir
        self.venv = venv

    def raw_manage(self, command_name, *args):
        """
        Allows the execution of arbitrary management commands on the remote
        host.

        One of the convenience methods is probably a cleaner interface for
        most usecases, however.
        """
        arguments = ' '.join(args)
        with cd(self.remote_project_dir), virtualenv(self.venv):
            run('./manage.py {cmd} {arguments}'.format(
                cmd=command_name,
                arguments=arguments))

    def collectstatic(self):
        """
        Performs the ``collectstatic`` management command on the remote host.
        """
        self.raw_manage('collectstatic', '--noinput')

    def syncdb(self):
        """
        Performs the ``syncdb`` management command on the remote host.

        .. warning::

           ``syncdb`` itself becomes deprecated with Django 1.7 and as
           such the new ``migrate`` should be used at that point.
        """
        self.raw_manage('syncdb', '--noinput')


def run_script(script, use_sudo=False):
    """
    Run the local script on the remote server.
    """
    put(script, script, mode=0755)
    if use_sudo:
        runner = sudo
    else:
        runner = run

    return runner('./{script}'.format(script=script))


def start_celery(repo_dir, deployment_id):
    run('mkdir -p celery')
    with hide('output', 'running'):
        home_directory = run('echo $HOME')
    run('mkdir -p celery')
    celery_exe = os.path.join(
        home_directory,
        '.virtualenvs',
        env.conf['virtualenv'],
        'bin',
        'celery')
    project_dir = os.path.join(
        home_directory,
        repo_dir,
        'tca')
    supervisord_config = {
        'command': celery_exe + ' -A tca worker -l info',
        'directory': project_dir,
        'stdout_logfile': os.path.join(home_directory, 'celery', 'log'),
        'stderr_logfile': os.path.join(home_directory, 'celery', 'log'),
        'autostart': 'true',
        'autorestart': 'true',
        'stopwaitsecs': '10',
        'startsecs': '10',
        'killasgroup': 'true',
        'stopasgroup': 'true',
    }

    supervisor = Supervisor(env.conf['supervisord']['conf.d'])
    supervisor.register_to_supervisor(
        'celery-' + deployment_id,
        supervisord_config)
    supervisor.reload()


def register_to_supervisor(repo_dir, deployment_id):
    with hide('output', 'running'):
        home_directory = run('echo $HOME')
    run('mkdir -p gunicorn')
    scripts_dir = os.path.join(
        home_directory,
        repo_dir,
        'scripts')

    supervisord_config = {
        'command': (
            'python run_gunicorn_server.py'
            ' --socket-name={socket_name}'.format(
                socket_name=deployment_id)
        ),
        'directory': scripts_dir,
        'user': env.user,
        'autostart': 'True',
        'autorestart': 'True',
        'redirect_stderr': 'True',
        'stopasgroup': 'True',
    }

    supervisor = Supervisor(env.conf['supervisord']['conf.d'])
    supervisor.register_to_supervisor(deployment_id, supervisord_config)
    supervisor.reload()


def register_to_nginx(repo_dir, deployment_id):
    # Read the template and fill it out
    with open('nginx_conf_template.conf', 'r') as f:
        template = f.read()

    conf = template.format(
        deployment_id=deployment_id,
        static_dir=env.conf['django_settings']['STATIC_ROOT'],
        server_name=env.conf['django_settings']['TCA_DOMAIN_NAME'])

    nginx = Nginx(env.conf['nginx']['etc'])
    nginx.add_site(deployment_id, conf)
    nginx.restart()


@task
def provision():
    run_script('provision.sh', use_sudo=True)


@task
def set_up_project():
    print yellow("Creating a the deployment directory")
    deployment_dir = env.conf['deployment_dir']
    run('mkdir -p {dir}'.format(dir=deployment_dir))

    print yellow("Checking out the project")
    with cd(deployment_dir):
        git.clone(env.conf['git']['url'], env.conf['project_name'])
    repo_dir = os.path.join(deployment_dir, env.conf['project_name'])

    # Project dependencies
    print yellow("Creating a new virtualenv for the project")
    with prefix('source `which virtualenvwrapper.sh`'), hide('output'):
        run('mkvirtualenv {venv}'.format(venv=env.conf['virtualenv']))
    print yellow("Installing project requirements to a virtualenv")
    venv_name = env.conf['virtualenv']
    with cd(repo_dir), virtualenv(venv_name), hide('output'):
        run(pip.requirements('tca/requirements.txt'))

    # Project settings
    print yellow("Setting up project settings")
    project_dir = os.path.join(repo_dir, 'tca')
    settings_dir = os.path.join(
            project_dir,
            'tca',
            'settings')
    with cd(settings_dir), hide('output', 'running'):
        run("cp production.template.py production.py")
        run("echo '{settings}' >>production.py".format(
            settings=get_django_settings(env.conf['django_settings'])))
        run("ln -s production.py local_settings.py")

    django_manage = DjangoProjectConfigurator(project_dir, venv_name)
    # Collect static
    print yellow("Collect static files")
    django_manage.collectstatic()

    # Migrate DB
    print yellow("Initial database migration")
    django_manage.syncdb()

    # Run celery
    start_celery(repo_dir, env.conf['deployment_id'])

    # Register in supervisord
    register_to_supervisor(repo_dir, env.conf['deployment_id'])

    # Register in nginx
    register_to_nginx(repo_dir, env.conf['deployment_id'])

    print green("Deployment complete")


@task
def stop_deployment():
    """
    Stops the the deployment on the remote host.
    """
    supervisor = Supervisor(env.conf['supervisord']['conf.d'])
    deployment_id = env.conf['deployment_id']
    supervisor.stop('celery-' + deployment_id)
    supervisor.stop(deployment_id)
    nginx = Nginx(env.conf['nginx']['etc'])
    nginx.disable_site(deployment_id)
    nginx.restart()

    print green("Stopped the deployment")


@task
def start_deployment():
    """
    Starts a stopped deployment
    """
    supervisor = Supervisor(env.conf['supervisord']['conf.d'])
    deployment_id = env.conf['deployment_id']
    supervisor.start('celery-' + deployment_id)
    supervisor.start(deployment_id)
    nginx = Nginx(env.conf['nginx']['etc'])
    nginx.enable_site(deployment_id)
    nginx.restart()

    print green("Started the deployment")
