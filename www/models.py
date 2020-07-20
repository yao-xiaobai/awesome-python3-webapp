#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time,uuid
from orm import Model,IntegerField,StringField,BooleanField,TextField,FloatField

def next_id():
    return '%015d%s000'%(int(time.time()*1000),uuid.uuid4().hex)

class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True,column='varchar(50)',default=next_id)
    email = StringField(column='varchar(50)')
    password = StringField(column='varchar(50)')
    admin = BooleanField()
    name = StringField(column='varchar(50)')
    image = StringField(column='varchar(500)')
    create_at = FloatField(default=time.time)

class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True,default=next_id,column='varchar(50)')
    user_id = StringField(column='varchar(50)')
    user_name = StringField(column='varchar(50)')
    user_image = StringField(column='varchar(500)')
    name = StringField(column='varchar(50)')
    summary = StringField(column='varchar(200)')
    content = TextField()
    create_at = FloatField(default=time.time)

class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True,default=next_id,column='varchar(50)')
    blog_id = StringField(column='varchar(50)')
    user_id = StringField(column='varchar(50)')
    user_name = StringField(column='varchar(50)')
    user_image = StringField(column='varchar(500)')
    content = TextField()
    create_at = FloatField(default=time.time)
