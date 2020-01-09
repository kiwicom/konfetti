from __future__ import absolute_import

import attr

from .. import Konfig


class FlaskKonfig(object):
    __slots__ = ("konfig", "kwargs")

    def __init__(self, app=None, konfig=None, **kwargs):
        self.konfig = konfig or Konfig(strict_override=False)
        self.kwargs = kwargs
        if app:
            self.init_app(app)

    def init_app(self, app, **kwargs):
        self.kwargs.update(kwargs)
        app.config = self.make_config(app)

    def make_config(self, app):
        return KonfigProxy(self.kwargs, flask_config=app.config, konfig=self.konfig)


@attr.s(slots=True)
class KonfigProxy(object):
    kwargs = attr.ib()
    flask_config = attr.ib()
    konfig = attr.ib()

    def get(self, key, default=None):
        try:
            return self._get(key)
        except KeyError:
            return default

    def _get(self, key):
        try:
            return self.kwargs[key]
        except KeyError:
            try:
                return getattr(self.konfig, key)
            except AttributeError:
                return self.flask_config[key]

    def __getitem__(self, item):
        return self._get(item)

    def __setitem__(self, key, value):
        self.flask_config[key] = value

    def __contains__(self, item):
        return self.get(item) is not None

    def __getattr__(self, item):
        try:
            return getattr(self.flask_config, item)
        except AttributeError:
            return self[item]
