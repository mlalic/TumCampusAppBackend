from django.test import TestCase

from django.core.urlresolvers import reverse
from urllib import urlencode

import json


class ViewTestCaseMixin(object):
    """A mixin providing some convenience methods for testing views.

    Expects that a ``view_name`` property exists on the class which
    mixes it in.
    """

    def get_view_url(self, *args, **kwargs):
        return reverse(self.view_name, args=args, kwargs=kwargs)

    def build_url(self, base_url, query_dict=None):
        url_template = "{base_url}?{query_string}"

        if query_dict is None:
            return base_url

        return url_template.format(
            base_url=base_url,
            query_string=urlencode(query_dict)
        )

    def get(self, parameters=None, *args, **kwargs):
        """
        Sends a GET request to the view-under-test and returns the response

        :param parameters: The query string parameters of the GET request
        """
        base_url = self.get_view_url(*args, **kwargs)

        return self.client.get(self.build_url(base_url, parameters))

    def post(self, body=None, content_type='application/json', *args, **kwargs):
        """
        Sends a POST request to the view-under-test and returns the response

        :param body: The content to be included in the body of the request
        """
        base_url = self.get_view_url(*args, **kwargs)

        if body is None:
            body = ''

        return self.client.post(
            self.build_url(base_url),
            body,
            content_type=content_type)

    def post_json(self, json_payload, *args, **kwargs):
        """
        Sends a POST request to the view-under-test and returns the response.
        The body of the POST request is formed by serializing the
        ``json_payload`` object to JSON.
        """
        payload = json.dumps(json_payload)

        return self.post(
            body=payload,
            content_type='application/json',
            *args, **kwargs)
