#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import functools,inspect,asyncio,os
from aiohttp import web
from urllib import parse
from apis import APIError
import logging
logging.basicConfig(format='%(asctime)s: %(message)s',datefmt='%y-%b-%d %H:%M:%S',level=logging.INFO)

#**************************************** URL 函数装饰器 **************************************

''' 
    建立视图函数装饰器，用于存储，附带URL信息
'''

#Get 方法装饰器
def get(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

#Post 方法装饰器
def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


#*********************************** Request Handle **********************************

'''
    编写 request handler,以用来处理url函数中获取request参数
'''

'''
    1. 定义解析视图函数参数的几个函数
'''

#获取没有默认值的命名关键字参数
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

#获取所有命名关键字参数
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

#检测是否有命名关键字参数
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

#检测是否有关键字参数
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

#检测是否有'request'参数,且'request'参数必须在位置参数之后
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        # 如果以下判断为 true，则params只能是位置参数。且该参数位于 request 之后，不满足条件，报错
        if found and ( param.kind != inspect.Parameter.KEYWORD_ONLY 
                        and param.kind != inspect.Parameter.VAR_KEYWORD 
                        and param.kind != inspect.Parameter.VAR_POSITIONAL):
            raise ValueError('request parameter must be the last named parameter in function: %s(%s)' % (fn.__name__, str(sig)))
    return found


'''
    提取 request 中的参数
    request是经aiohttp包装的一个对象,本质是一个HTTP请求,有请求状态(status),请求首部(Header),请求实体(Body)构成
'''

class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)         #是否有 'request' 参数
        self._has_var_kw_arg = has_var_kw_arg(fn)         #是否有关键字参数
        self._has_named_kw_args = has_named_kw_args(fn)     #是否有命名关键字参数
        self._named_kw_args = get_named_kw_args(fn)         #获取所有命名关键字参数
        self._required_kw_args = get_required_kw_args(fn)   #获取所有未设置默认值的命名关键字参数

    async def __call__(self, request):
        kw = None
        if self._has_named_kw_args or self._has_var_kw_arg:    #命名关键字or 关键字参数
            if request.method == 'POST':                        #判断客户端发来的是否为POST方法
                if not request.content_type:                    #检测是否提交数据格式
                    return web.HTTPBadRequest(text='Missing Content-Type')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):            #请求消息主题是序列化后的json字符串
                    params = await request.json() 
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text='Json body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content-Type:%s'%request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]

        if kw is None:
            kw = dict(**request.match_info)
        else:
            #有命名关键字参数，没有关键字参数
            if not self._has_var_kw_arg and self._named_kw_args:
                copy = dict()
                #只保留命名关键字参数
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw arg:%s'%k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest(text='Missing argument:%s'%name)
        #至此，kw为视图函数fn正真能调用的参数，request请求中的参数终于传递给了视图函数
        logging.info('call with args: %s' % str(kw))    

        try:
            r = await self._func(**kw)
            return r
        except APIError as e: 
            return dict(error=e.error, data=e.data, message=e.message)            


#************************************编写注册函数*****************************

'''
    编写静态文件注册函数
    编写 add_static 函数用于注册静态文件，只提供路径名即可添加注册
    添加静态文件，如image,css,javascript等
'''  

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
    app.router.add_static('/static/',path)
    logging.info('add static %s => %s'%('/static/',path))

#编写一个add_route函数，用来注册一个视图函数
def add_route(app,fn):
    method = getattr(fn,'__method__',None)
    path = getattr(fn,'__route__',None)
    if path is None or method is None:
        raise ValueError('@get or @post is not defined in function:%s'%fn.__name__)
    #将非协程和非生成器的注册函数转换成协程
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)'%(method,path,fn.__name__,','.join(inspect.signature(fn).parameters.keys())))
    #在app中注册经RequestHandler封装后的注册函数
    app.router.add_route(method,path,RequestHandler(app,fn))

#导入模块，批量注册视图函数
def add_routes(app, module_name):
    #检测module_name是否是 a.b 形式
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    #dir()迭代出mod模块中所有类，实例，函数等
    for attr in dir(mod):
        #忽略以'_'开头的对象
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        #确保 fn 是函数
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            #对 fn 进行注册
            if method and path:
                add_route(app, fn)
