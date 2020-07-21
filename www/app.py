#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio,os,json,time,datetime
from aiohttp import web
from datetime import datetime
from jinja2 import Environment,FileSystemLoader
from handlers import cookie2user,COOKIE_NAME

from coroweb import add_routes,add_static
import orm

import logging
logging.basicConfig(format='%(asctime)s: %(message)s',datefmt='%y-%b-%d %H:%M:%S',level=logging.INFO)


#初始化jinja
def init_jinja2(app,**kw):
    logging.info('init jinja2...')
    #配置options参数
    options = dict(
        #自动转义 xml/html 的特殊字符
        autoescape = kw.get('autoescape',True),
        #代码块的开始结束标志
        block_start_string = kw.get('block_start_string','{%'),
        block_end_string = kw.get('block_end_string','%}'),
        #变量的开始结束标志
        variable_start_string = kw.get('variable_start_string','{{'),
        variable_end_string = kw.get('variable_end_string','}}'),
        #自动加载修改后的模板文件
        auto_reload = kw.get('auto_reload',True)
    )

    #获取模板文件夹路径
    path = kw.get('path',None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    # Environment类是jinja2的核心类，用来保存配置、全局对象以及模板文件的路径
	# FileSystemLoader类加载path路径中的模板文件
    env = Environment(loader=FileSystemLoader(path),**options)
    #过滤器集合
    filters = kw.get('filters',None)
    if filters is not None:
        for name,f in filters.items():
            env.filters[name] = f
    #所有一切都是给 app 添加 templating 字段
    #前段将jinja的环境配置全都赋予给env变量，此处再将env赋给app dict对象，这样app就知道去哪找和解析模板
    app['__templating__'] = env

#编写一个时间过滤器
def datetime_filter(t):
    dis = int(time.time() - t)
    if dis < 60:
        return '1分钟前'
    elif dis < 3600:
        return '%s分钟前'%(dis//60)
    elif dis < 86400:
        return '%s小时前'%(dis//3600)
    elif dis <604800:
        return '%s天前'%(dis//86400)
    else:
        dt = datetime.fromtimestamp(t)
        return '%s年%s月%s日前'%(dt.year,dt.month,dt.day)

# middleware 拦截器
# 一个URL函数在被处理前，可以经过一系列 middleware 处理


async def logger_factory(app,handler):
    async def logger(request):
        logging.info('Request:%s %s'%(request.method,request.path))
        return (await handler(request))
    return logger

async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

#提取并解析cookie并绑定到request对象
async def auth_factory(app,handler):
    async def auth(request):
        logging.info('check user:%s %s'%(request.method,request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user:%s'%user.email)
                request.__user__ = user
        if request.path.startswith('/manage/') and ( request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return ( await handler(request) )
    return auth

async def response_factory(app,handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r,web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__',None)
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                # app['__templating__']获取已初始化的Environment对象，调用get_template()方法返回Template对象
                # 调用Template对象的render()方法，传入r渲染模板，返回unicode格式字符串，将其用utf-8编码 
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='root', password='Yxt123456!', db='awesome')
    app = web.Application(loop=loop, middlewares=[
        logger_factory,auth_factory,response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
