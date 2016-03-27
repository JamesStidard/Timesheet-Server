from timesheet.model.log import Log
from timesheet.model.integration import Integration
from timesheet.handlers.base_handler import BaseHandler
from timesheet.utils.user_session import async_user_session
from timesheet.utils.log_exceptions import IncompleteLogException
from timesheet.dispatches.insert_log import insert_log
from timesheet.dispatches.update_log import update_log
from timesheet.dispatches.delete_log import delete_log

__author__ = 'James Stidard'


class LogHandler(BaseHandler):

    @async_user_session
    async def get(self, user, session):
        logs = session.query(Log).filter(Log.user_id == user.id).all()
        self.write([l.client_format for l in logs])

    @async_user_session
    async def post(self, user, session):
        kwargs = self.get_json_arguments(
            ('integration_id'),
            ('project_id'),
            ('task'),
            ('start', None),
            ('end', None),
            ('billable', True),
            ('notes', None),
        )

        integration_id = kwargs.pop('integration_id')
        integration    = session.query(Integration)\
                                .filter(Integration.user_id == user.id,
                                        Integration.id == integration_id).one()

        log = integration.Log(user=user, integration=integration, **kwargs)
        session.add(log)
        session.flush()

        try:
            log.zoho_id = await insert_log(integration)
        except IncompleteLogException:
            pass

        self.write(log.client_format)

    @async_user_session
    async def put(self, user, session):
        log_id = self.get_json_argument('id')
        log    = session.query(Log)\
                        .filter(Log.user_id == user.id,
                                Log.id == log_id).one()

        for property_key in ['task', 'start', 'end', 'billable', 'notes']:
            if property_key in self.json_arguments:
                value = self.get_json_argument(property_key)
                log.__setattr__(property_key, value)

        session.flush()

        if not log.zoho_id:
            try:
                log.zoho_id = await insert_log(log)
            except IncompleteLogException:
                pass
        else:
            try:
                log.zoho_id = await update_log(log)
            except IncompleteLogException:
                log.zoho_id = await delete_log(log)  # Set zoho_id to None
                pass

        self.write(log.client_format)

    @async_user_session
    async def delete(self, user, session):
        log_id = self.get_argument('id')
        log    = session.query(Log)\
                        .filter(Log.user_id == user.id,
                                Log.id == log_id).one()

        if log.zoho_id:
            await delete_log(log)

        session.delete(log)
        session.flush()

        self.write('Success')
