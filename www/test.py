# -*- coding: utf-8 -*-
# @author xian_wen
# @date 5/31/2021 11:14 PM

import asyncio
import orm
from models import User


async def test():
    await orm.create_pool(user='root', password='password', db='awesome')
    a = User(name='Administrator', email='admin@example.com', password='1234567890', image='about:blank')
    x = User(name='xian_wen', email='xian_wen@example.com', password='1234567890', image='about:blank')
    t = User(name='Test', email='test@example.com', password='1234567890', image='about:blank')
    await a.save()
    await x.save()
    await t.save()


loop = asyncio.get_event_loop()
loop.run_until_complete(test())
