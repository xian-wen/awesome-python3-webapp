# -*- coding: utf-8 -*-
# @author xian_wen
# @date 6/1/2021 12:26 PM

# import asyncio
import functools
import inspect
import logging
import os

from urllib import parse

from aiohttp import web

from apis import APIError


def get(path):
    """
    Define decorator @get('/path')

    :param path:
    :return:
    """

    def decorator(func):
        # 使得 wrapper.__name__ = func.__name__
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper

    return decorator


def post(path):
    """
    Define decorator @post('/path')

    :param path:
    :return:
    """

    def decorator(func):
        # 使得 wrapper.__name__ = func.__name__
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper

    return decorator


def get_required_kwargs(fn):
    """
    获取函数命名关键字参数，且非默认参数

    :param fn: function
    :return:
    """
    args = []
    # 获取函数 fn 的参数，ordered mapping
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # * 或者 *args 后面的参数，且没有默认值
        if param.kind == param.KEYWORD_ONLY and param.default is param.empty:
            args.append(name)
    return tuple(args)


def get_named_kwargs(fn):
    """
    获取函数命名关键字参数

    :param fn: function
    :return:
    """
    args = []
    # 获取函数 fn 的参数，ordered mapping
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # * 或者 *args 后面的参数
        if param.kind == param.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


def has_named_kwarg(fn):
    """
    判断是否有命名关键字参数

    :param fn: function
    :return:
    """
    # 获取函数 fn 的参数，ordered mapping
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # * 或者 *args 后面的参数
        if param.kind == param.KEYWORD_ONLY:
            return True


def has_var_kwarg(fn):
    """
    判断是否有关键字参数

    :param fn: function
    :return:
    """
    # 获取函数 fn 的参数，ordered mapping
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # **args 后面的参数
        if param.kind == param.VAR_KEYWORD:
            return True


def has_request_arg(fn):
    """
    判断是否有请求参数

    :param fn: function
    :return:
    """
    # 获取函数 fn 的签名
    sig = inspect.signature(fn)
    # 获取函数 fn 的参数，ordered mapping
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind is not param.VAR_POSITIONAL and
                      param.kind is not param.KEYWORD_ONLY and
                      param.kind is not param.VAR_KEYWORD):
            # fn(*args, **kwargs)，fn 为 fn.__name__，(*args, **kwargs) 为 sig
            raise ValueError(
                'Request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found


class RequestHandler(object):

    def __init__(self, app, fn):
        self.__app = app
        self.__func = fn
        self.__has_request_arg = has_request_arg(fn)
        self.__has_var_kwarg = has_var_kwarg(fn)
        self.__has_named_kwarg = has_named_kwarg(fn)
        self.__named_kwargs = get_named_kwargs(fn)
        self.__required_kwargs = get_required_kwargs(fn)

    # Make RequestHandler callable
    async def __call__(self, request):
        kwargs = None
        if self.__has_var_kwarg or self.__has_named_kwarg or self.__required_kwargs:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest(text='Missing Content-Type.')
                ct = request.content_type.lower()
                # JSON 数据格式
                if ct.startswith('application/json'):
                    # Read request body decoded as json
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text='JSON body must be dict object.')
                    kwargs = params
                # form 表单数据被编码为 key/value 格式发送到服务器（表单默认的提交数据的格式）
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    # Read POST parameters from request body
                    params = await request.post()
                    kwargs = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                # The query string in the URL, e.g., id=10
                qs = request.query_string
                if qs:
                    kwargs = dict()
                    # {'id': ['10']}
                    for k, v in parse.parse_qs(qs, True).items():
                        kwargs[k] = v[0]
        if kwargs is None:
            kwargs = dict(**request.match_info)
        else:
            if not self.__has_var_kwarg and self.__named_kwargs:
                # Remove all unnamed kwargs
                copy = dict()
                for name in self.__named_kwargs:
                    if name in kwargs:
                        copy[name] = kwargs[name]
                kwargs = copy
            # Check named kwargs
            for k, v in request.match_info.items():
                if k in kwargs:
                    logging.warning('Duplicate arg name in named kwargs and kwargs: %s' % k)
                kwargs[k] = v
        if self.__has_request_arg:
            kwargs['request'] = request
        # Check required kwargs
        if self.__required_kwargs:
            for name in self.__required_kwargs:
                if name not in kwargs:
                    return web.HTTPBadRequest(text='Missing argument: %s' % name)
        logging.info('Call with kwargs: %s' % str(kwargs))
        try:
            r = await self.__func(**kwargs)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_static(app):
    # /www/static
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    # Add a router and a handler for returning static files
    # Development only, in production, use web servers like nginx or apache
    app.router.add_static('/static/', path)
    logging.info('Add static %s => %s' % ('/static/', path))


def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
    #     fn = asyncio.coroutine(fn)
    logging.info(
        # GET / => fn(*args, **kwargs)
        'Add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # Attention: handler is converted to coroutine internally when it is a regular function
    app.router.add_route(method, path, RequestHandler(app, fn))


def add_routes(app, module_name):
    # For package.module, n = 7
    # For module, n = -1
    n = module_name.rfind('.')
    if n == -1:
        # Import module
        mod = __import__(module_name, globals(), locals())
    else:
        # For package.module, name = module
        name = module_name[n + 1:]
        # Import package.module, the same as 'from package import module', fromlist = [module]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    # Directory of attributes of module
    for attr in dir(mod):
        if attr.startswith('__'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)
