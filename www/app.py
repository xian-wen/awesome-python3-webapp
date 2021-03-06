# -*- coding: utf-8 -*-
# @author xian_wen
# @date 5/26/2021 2:06 PM

import json
import logging
import os
import time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static
from config import configs
from handlers import COOKIE_NAME, cookie2user

logging.basicConfig(level=logging.INFO)


def init_jinja2(app, **kwargs):
    logging.info('Init jinja2...')
    options = dict(
        autoescape=kwargs.get('autoescape', True),
        block_start_string=kwargs.get('block_start_string', '{%'),
        block_end_string=kwargs.get('block_end_string', '%}'),
        variable_start_string=kwargs.get('variable_start_string', '{{'),
        variable_end_string=kwargs.get('variable_end_string', '}}'),
        auto_reload=kwargs.get('auto_reload', True)
    )
    path = kwargs.get('path', None)
    if path is None:
        # /www/templates
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('Set jinja2 template path: %s' % path)
    # Load templates from a directory in the file system
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kwargs.get('filters', None)
    if filters is not None:
        # Filters are Python functions
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env


async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        return await handler(request)

    return logger


async def auth_factory(app, handler):
    async def auth(request):
        logging.info('Check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('Set current user: %s' % user.email)
                request.__user__ = user
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return await handler(request)

    return auth


async def data_factory(app, handler):
    async def parse_data(request):
        # JSON ????????????
        if request.content_type.startswith('application/json'):
            # Read request body decoded as json
            request.__data__ = await request.json()
            logging.info('Request json: %s' % str(request.__data__))
        # form ???????????????????????? key/value ??????????????????????????????????????????????????????????????????
        elif request.content_type.startswith('application/x-www-form-urlencoded'):
            # Read POST parameters from request body
            request.__data__ = await request.post()
            logging.info('Request form: %s' % str(request.__data__))
        return await handler(request)

    return parse_data


async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        # The base class for the HTTP response handling
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            # ????????????????????????????????????????????????
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            # HTML ??????
            resp.content_type = 'text/html; charset=UTF-8'
            return resp
        # Response classes are dict like objects
        if isinstance(r, dict):
            # ????????????
            template = r.get('__template__')
            if template is None:
                resp = web.Response(
                    # ensure_ascii: if false then return value can contain non-ASCII characters
                    # __dict__: store an object???s (writable) attributes
                    # ????????? r ??? json ????????????default ????????????????????????????????????????????? JSON ?????????
                    body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                # JSON ????????????
                resp.content_type = 'application/json; charset=UTF-8'
                return resp
            else:
                # app[__templating__] ????????? Environment ????????????????????????????????????
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html; charset=UTF-8'
                return resp
        # Status Code
        if isinstance(r, int) and 100 <= r < 600:
            return web.Response(status=r)
        # Status Code and Reason Phrase
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and 100 <= t < 600:
                # 1xx: Informational - Request received, continuing process
                # 2xx: Success - The action was successfully received, understood, and accepted
                # 3xx: Redirection - Further action must be taken in order to complete the request
                # 4xx: Client Error - The request contains bad syntax or cannot be fulfilled
                # 5xx: Server Error - The server failed to fulfill an apparently valid request
                return web.Response(status=t, reason=str(m))
        # Default
        resp = web.Response(body=str(r).encode('utf-8'))
        # ???????????????
        resp.content_type = 'text/plain; charset=UTF-8'
        return resp

    return response


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:  # 1 min
        return u'1?????????'
    if delta < 3600:  # 1 h
        # // ????????????????????? 3 / 2 = 1.5???3 // 2 = 1
        return u'%s?????????' % (delta // 60)
    if delta < 86400:  # 24 h
        return u'%s?????????' % (delta // 3600)
    if delta < 604800:  # 7 days
        return u'%s??????' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s???%s???%s???' % (dt.year, dt.month, dt.day)


async def init_db(app):
    # If on Linux, use another user instead of 'root'
    await orm.create_pool(
        host=configs.db.host,
        port=configs.db.port,
        user=configs.db.user,
        password=configs.db.password,
        db=configs.db.database
    )


app = web.Application(middlewares=[
    logger_factory,
    auth_factory,
    response_factory
])
init_jinja2(app, filters=dict(datetime=datetime_filter))
add_routes(app, 'handlers')
add_static(app)
app.on_startup.append(init_db)
web.run_app(app, host='localhost', port=9000)
