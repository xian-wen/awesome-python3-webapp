# -*- coding: utf-8 -*-
# @author xian_wen
# @date 6/3/2021 11:37 AM

from coroweb import get

from models import User


@get('/')
async def index(request):
    users = await User.find_all()
    return {
        '__template__': 'test.html',
        'users': users
    }
