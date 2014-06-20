"""
A template for settings which should be used in production.

In order for the settings to be truly useful, they need to be
filled out with corresponding values.

Use the template to create a ``production.py`` file and then create
a symlink to it from a ``local_settings.py`` file, i.e.::

    settings/local_settings.py -> settings/production.py
"""

#: Make sure to provide a real celery broker
# BROKER_URL = 'amqp://guest:guest@localhost//'
