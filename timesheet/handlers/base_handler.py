import json
from json.decoder import JSONDecodeError
from urllib.parse import urlparse

from tornado.web import RequestHandler
from tornado.web import HTTPError

from timesheet.model.token import Token
from timesheet.utils.http_exceptions import MissingArgumentsError

__author__ = 'James Stidard'


class BaseHandler(RequestHandler):

    def initialize(self):
        import logging
        logging.info('initialise')

    @property
    def origin_whitelist(self):
        return self.application.settings.get('cors_origins')

    @property
    def control(self):
        return self.application.settings.get('control')

    def get_current_user(self):
        try:
            return self.get_secure_cookie("user_id").decode('utf-8')
        except AttributeError:
            try:
                token_id     = self.request.headers.get('token-id')
                token_secret = self.request.headers.get('token-secret')
                with self.control.session as session:
                    token = session.query(Token)\
                                   .filter(Token.id == token_id)\
                                   .one()
                    token.authenticate(token_secret)
                    session.commit()
                    return token.user_id
            except ValueError:
                raise MissingArgumentsError('Not already logged in or incorrect\
                                            auth id and token provided.')

    @property
    def request_origin(self):
        url = self.request.headers.get("Referer")
        if url:
            o = urlparse(url)
            origin = o.scheme + "://" + o.hostname
            if o.port:
                origin = "{}:{}".format(origin, o.port)
            return origin

    def write(self, chunk):
        super().write({
            'result': chunk
        })

    def write_error(self, status_code, reason=None, exc_info=None, **kwargs):
        if not reason and exc_info:
            _, exception, _ = exc_info
            reason = exception.reason

        self.write(reason)

    def prepare(self):
        try:
            self.json_arguments = json.loads(self.request.body.decode('utf-8'))
        except JSONDecodeError:
            self.json_arguments = {}

    def get_json_argument(self,
                          name: str,
                          default=RequestHandler._ARG_DEFAULT):
        try:
            return self.json_arguments[name]
        except Exception:
            if default is RequestHandler._ARG_DEFAULT:
                raise MissingArgumentsError(name)
            else:
                return default

    def get_json_arguments(self, *arguments, strict=False):
        """
        Arguments should either be a tuple with the structure
        (arg_name, default) or just a str of the arguments name.

        If a default is provided, the default will be returned if value for
        argument doesn't exist. Otherwise, when no default is present, a
        MissingArguemntsError exception will be raised.
        """
        results = []
        missing = []

        for argument in arguments:
            if isinstance(argument, str):
                argument = (argument, )  # Simple str arguments to tuple

            try:
                result = self.get_json_argument(*argument)
            except MissingArgumentsError as exc:
                missing.extend(exc.arg_names)
            else:
                results.append(result)

        if missing:
            raise MissingArgumentsError(*missing)
        else:
            return results

    def get_argument(self,
                     name: str,
                     default=RequestHandler._ARG_DEFAULT,
                     strip: bool=True,
                     cast: type=None):
        try:
            value = super().get_argument(name, strip=True)
            return cast(value) if cast else value
        except MissingArgumentsError:
            if default is RequestHandler._ARG_DEFAULT:
                raise MissingArgumentsError(name)
            else:
                return default

    def set_default_headers(self):
        if self.request_origin in self.origin_whitelist:
            self.set_header("Access-Control-Allow-Origin", self.request_origin)
            self.set_header('Access-Control-Allow-Credentials', 'true')

    def options(self):
        if self.request_origin in self.origin_whitelist:
            self.set_header("Access-Control-Allow-Origin", self.request_origin)
            self.set_header('Access-Control-Allow-Credentials', 'true')
            self.set_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
            self.set_header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Key, Cache-Control')
            self.set_header('Access-Control-Max-Age', 3000)
            self.set_status(204)
            self.finish()
        else:
            raise HTTPError(403)
