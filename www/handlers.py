#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re, time, json, logging, hashlib, base64, asyncio
from aiohttp import web
import markdown2
from coroweb import get, post
from apis import APIValueError, APIResourceNotFoundError,APIError,APIPermissionError,Page
from models import User, Comment, Blog, next_id
from config import configs,toDict
import logging
logging.basicConfig(level=logging.INFO,format='%(asctime)s: %(message)s',datefmt='%y-%b-%d %H:%M:%S')

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

#检测是否登录且是管理员
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except Exception as e:
        pass
    if p < 1:
        p = 1
    return p


def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
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
        s = '%s-%s-%s-%s' % (uid,user.password,expires,_COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.password = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

#首页
@get('/')
async def index(request,*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findnum('count(id)')
    num = num[0].get('count(id)',None)
    page = Page(num)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findall(orderby='create_at desc', limit=(page.offset, page.limit))
    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs,
        '__user__':request.__user__
    }

#点击某个blog，进入该blog的主页面
@get('/blog/{id}')
async def get_blog(id,request):
    blog = await Blog.find(id)
    comments = await Comment.findall(where='blog_id=?',args=[id],orderby='create_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__':'blog.html',
        'blog':blog,
        'comments':comments,
        '__user__':request.__user__
    }

#注册页，提交表单后会跳转至'api/users'视图函数
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

#登录页，提交表单后会跳转至'api/authenticate'视图函数
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

#注册API
@post('/api/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findall(selectField='email',where='email=?',args=[email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, password=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

#登录API
@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = await User.findall(where='email=?', args=[email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.password != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

#退出登录
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    #返回前一页或者首页
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

#拦截器会对返回结果进行处理，最终返回'/manage/comments'页
@get('/manage/')
def manage():
    return 'redirect:/manage/comments'

#后台管理页，评论页
@get('/manage/comments')
def manage_comments(request,*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page),
        '__user__':request.__user__
    }

#后台管理页，blog页
@get('/manage/blogs')
def manage_blogs(request,*,page='1'):
    return {
        '__template__':'manage_blogs.html',
        'page_index':get_page_index(page),
        '__user__':request.__user__
    }

#后台管理页，创建blog页
@get('/manage/blogs/create')
def manage_create_blog(request):
    return {
        '__template__':'manage_blog_edit.html',
        'id':'',
        'action':'/api/blogs',
        '__user__':request.__user__
    }

#后台管理页，编辑blog页
@get('/manage/blogs/edit')
def manage_edit_blog(request,*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id,
        '__user__':request.__user__
    }

#后台管理页，查看注册用户页
@get('/manage/users')
def manage_users(request,*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page),
        '__user__':request.__user__
    }

#获取评论,以json文件形式显示
@get('/api/comments')
async def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findnum('count(id)')
    num = num[0].get('count(id)',None)
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findall(orderby='create_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)

#创建评论
@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first.')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = await Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    await comment.save()
    return comment

#后台管理，删除评论
@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    check_admin(request)
    c = await Comment.find(id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    await c.remove(pk=id)
    return dict(id=id)

#以json形式返回所有注册用户
@get('/api/users')
async def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = await User.findnum('count(id)')
    num = num[0].get('count(id)',None)
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findall(orderby='create_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.password= '******'
    return dict(page=p, users=users)

#以json形式显示所有blog
@get('/api/blogs')
async def api_blogs(*,page='1'):
    page_index = get_page_index(page)
    num = await Blog.findnum(selectField='count(id)')
    num = num[0].get('count(id)',None)
    p = Page(num,page_index)
    if num == 0:
        return dict(page=0,blog=())
    blogs = await Blog.findall(orderby='create_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

#以json形式显示某个id的blog
@get('/api/blogs/{id}')
async def api_get_blog(*,id):
    blog = await Blog.find(id)
    return blog

#创建blog
@post('/api/blogs')
async def api_create_blog(request,*,name,summary,content):
    #检查是否登录且是管理员
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name','name cannot be empty')
    if not summary or not summary.strip():
        raise APIValueError('summary','summary cannot be empty')
    if not content or not content.strip():
        raise APIValueError('content','content connet be empty')
    blog = Blog(user_id=request.__user__.id,user_name=request.__user__.name,user_image=request.__user__.image,name=name.strip(),summary=summary.strip(),content=content.strip())
    await blog.save()
    return blog

#修改日志
@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, summary, content):
    check_admin(request)
    blog = await Blog.find(id)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog

#删除评论
@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
    check_admin(request)
    blog = await Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blogs')
    await blog.remove(pk=id)
    return dict(id=id)