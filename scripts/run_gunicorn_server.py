import subprocess
import argparse
import pwd
import os


def _get_user_home_dir(user):
    return os.path.expanduser('~' + user)


def build_parser():

    def _get_current_user():
        return pwd.getpwuid(os.getuid())[0]

    DEFAULTS = {
        'workers': 3,
        'user': _get_current_user(),
        'group': _get_current_user(),
        'log_file': os.path.join(
            _get_user_home_dir(_get_current_user()),
            'gunicorn',
            'tca.log'),
        'virtualenv': 'tca-dev',
    }


    parser = argparse.ArgumentParser()

    parser.add_argument('-w', '--workers', type=int,
                        default=DEFAULTS['workers'])
    parser.add_argument('--user', type=str,
                        default=DEFAULTS['user'])
    parser.add_argument('--group', type=str,
                        default=DEFAULTS['group'])
    parser.add_argument('--log-file', type=str,
                        default=DEFAULTS['log_file'])
    parser.add_argument('--virtualenv', type=str,
                        default=DEFAULTS['virtualenv'])
    parser.add_argument('--socket-name', type=str, required=True)

    return parser


def start_server(args):
    # Create the log directory, if necessary
    log_dir = os.path.dirname(args.log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Build the bind address
    # Make it a local UNIX socket instead of loopback TCP port
    bind_address = 'unix:/tmp/{socket_name}.socket'.format(
        socket_name=args.socket_name)

    # Activate the virtualenv
    activate_this_file = os.path.join(
        _get_user_home_dir(args.user),
        '.virtualenvs',
        args.virtualenv,
        'bin',
        'activate_this.py'
    )
    execfile(activate_this_file, dict(__file__=activate_this_file))

    # Start gunicorn processes -- spawns them and exits
    # NOTE: This makes the script dependent on the cwd.
    # TODO: Make it independent of the cwd.
    os.chdir('../tca')
    subprocess.call([
        'gunicorn',
        'tca.wsgi:application',
        '-b', bind_address,
        '-w', str(args.workers),
        '--user', args.user,
        '--group', args.group,
        '--log-file', args.log_file,
        '--log-level', 'debug',
    ])


if __name__ == '__main__':
    parser = build_parser()
    start_server(parser.parse_args())

