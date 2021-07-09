# -*- coding: utf-8 -*-
# @author xian_wen
# @date 6/3/2021 11:37 AM

import hashlib
import json
import logging
import re
import time

from aiohttp import web

from coroweb import get, post

from models import Blog, User, next_id
from apis import APIValueError, APIError
from config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret  # Awesome

_RE_EMAIL = re.compile(r'^[a-z0-9.-_]+@[a-z0-9-_]+(.[a-z0-9-_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[a-f0-9]{40}$')


def user2cookie(user, max_age):
    """
    Generate cookie str by user.

    :param user:
    :param max_age: lifetime of the cookie, in seconds
    :return: cookie string of id-expires-sha1
    """
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
    # sha1: 20 bytes, hexdigest(): 40 digits long
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


def make_cookie(user):
    """
    Set cookie.

    :param user:
    :return: response with cookie
    """
    r = web.Response()
    # httpOnly：使 Cookie 不被 JavaScript 读取，防止用户登录信息被引入的第三方恶意 js 代码窃取
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  # 24 h
    user.password = '******'
    r.content_type = 'application/json'
    # Serialize user to a json string, which can contain non-ASCII characters
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


async def cookie2user(cookie_str):
    """
    Parse cookie and load user if cookie is valid.

    :param cookie_str:
    :return:
    """
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('Invalid sha1')
            return None
        user.password = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None


@get('/')
async def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200),
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }


@get('/register')
async def register():
    return {
        '__template__': 'register.html'
    }


@get('/signin')
async def signin():
    return {
        '__template__': 'signin.html'
    }


@post('/api/authenticate')
async def authenticate(*, email, password):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not password:
        raise APIValueError('password', 'Invalid password.')
    users = await User.find_all('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # Check password
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(password.encode('utf-8'))
    if user.password != sha1.hexdigest():
        raise APIValueError('password', 'Invalid password.')
    # Authenticate ok, set cookie
    r = make_cookie(user)
    return r


@post('/api/users')
async def api_register_users(*, email, name, password):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not password or _RE_SHA1.match(password):
        raise APIValueError('password')
    users = await User.find_all('email=?', [email])
    if len(users) > 0:
        raise APIError('Register: failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_password = '%s:%s' % (uid, password)
    user = User(id=uid, name=name.strip(), email=email,
                password=hashlib.sha1(sha1_password.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # Make session cookie
    r = make_cookie(user)
    return r
