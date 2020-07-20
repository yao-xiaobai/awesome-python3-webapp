#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import aiomysql,asyncio
import logging
logging.basicConfig(format='%(asctime)s: %(message)s',datefmt='%y-%b-%d %H:%M:%S',level=logging.INFO)


#*********************************** SQL Operation ********************************#*******

#创建数据库连接池
async def create_pool(loop,**kw):  
    logging.info('Creating database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host','127.0.0.1'),         
        port = kw.get('port',3306),
        maxsize = kw.get('maxsize',10),             #最大连接数
        minsize = kw.get('minsize',1),              #最小连接数
        charset = kw.get('charset','utf8'),         #编码格式
        autocommit = kw.get('autocommit',True),     #自动提交
        db = kw['db'],
        user = kw['user'],
        password = kw['password'],
        loop = loop
    )

# select 子句
async def select(sql,args=(),size=None):
    logging.info('SQL:%s\nARGS:%s'%(sql,args))
    global __pool
    async with __pool.get() as connection:
        #从连接池获取连接
        cursor =await connection.cursor(aiomysql.DictCursor)
        #执行sql语句(语句与参数分离)
        await cursor.execute(sql.replace('?','%s'),args)
        #根据size(即记录的行数)返回查询结果
        if not size:
            res = await cursor.fetchall()
        else:
            res = await cursor.fetchmany(size)
        await cursor.close()
    logging.info('return rows:%s'%len(res))
    return res

# update,insert,delete 子句
async def execute(sql,args,autocommit=True):
    logging.info('SQL:%s\nARGS:%s'%(sql,args))
    global __pool
    async with __pool.get() as connection:
        if not autocommit:
            await connection.begin()
        try:
            cursor = await connection.cursor(aiomysql.DictCursor)
            await cursor.execute(sql.replace('?','%s'),args)
            rowcount = cursor.rowcount
            await cursor.close()
            logging.info('Affected rowcount:%s'%rowcount)
            if not autocommit:
                await connection.commit()
        except:
            if not autocommit:
                await connection.rollback()
            raise
    return rowcount

#**************************************** ORM *********************************************

# 字段父类
class Field(object):
    #name为字段名('id'),column为字段类型('bigint'),
    #primary_key为字段是否为主键(True/False),default为字段默认值
    def __init__(self,name,column,primary_key,default):
        self.name = name
        self.column = column
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s:%s:%s>'%(self.__class__.__name__,self.name,self.column)

# Integer 字段
class IntegerField(Field):
    def __init__(self,name=None,column='bigint',primary_key=False,default=None):
        super(IntegerField,self).__init__(name,column,primary_key,default)

# String 字段
class StringField(Field):
    def __init__(self,name=None,column='varchar(100)',primary_key=False,default=None):
        super(StringField,self).__init__(name,column,primary_key,default)

# Boolean 字段
class BooleanField(Field):
    def __init__(self,name=None,column='boolean',primary_key=False,default=False):
        super(BooleanField,self).__init__(name,column,False,default)

# Float 字段
class FloatField(Field):
    def __init__(self,name=None,column='real',primary_key=False,default=None):
        super(FloatField,self).__init__(name,column,primary_key,default)

# Text 字段
class TextField(Field):
    def __init__(self,name=None,column='text',primary_key=False,default=None):
        super(TextField,self).__init__(name,column,False,default)

#元类
class ModelMetaclass(type):
    def __new__(cls,name,bases,attrs):
        #排除子类为Model
        if name == 'Model':
            return type.__new__(cls,name,bases,attrs)
        #获取表名
        tableName = attrs.get('__table__',None) or name
        logging.info('Found Model:%s(tablename:%s)'%(name,tableName))
        mappings = dict()       #映射关系
        primarykey = None       #主键
        fields = []             #除主键外所有字段
        parameters = []         #sql形参,即？
        #找出字类所有属性方法，并用isinstance筛选出 Field 属性
        for k,v in attrs.items():
            if isinstance(v,Field):
                logging.info('Found mapping:%s->%s'%(k,v))
                mappings[k] = v
                parameters.append('?')
                #筛选主键字段，并且主键字段有且只能有一个
                if v.primary_key:
                    if primarykey:
                        raise RuntimeError('Duplicate primary key for Field:%s'%k)
                    primarykey = k
                #将非主键字段添加至fields中
                else:
                    fields.append(k)
        if not primarykey:
            raise RuntimeError('Primary key not found')
        for k in mappings.keys():
            attrs.pop(k)
        #构造update的表达式(''id'=?')
        field_exp = []
        for k in fields:
            l = '%s=?'%k
            field_exp.append(l)
        #保存属性
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primarykey
        attrs['__mappings__'] = mappings    #属性与列的映射关系
        attrs['__fields__'] = fields
        #选择数据
        attrs['__select__'] = 'select %s,%s from %s'%(primarykey,','.join(fields),tableName)
        #插入新数据
        attrs['__insert__'] = 'insert into %s(%s,%s)values (%s)'%(tableName,primarykey,','.join(fields),','.join(parameters))
        #根据主键更新记录 
        attrs['__update__'] = 'update %s set %s where %s=?'%(tableName,','.join(field_exp),primarykey)
        #根据主键删除记录
        attrs['__delete__'] = 'delete from %s where %s=?'%(tableName,primarykey)
        return type.__new__(cls,name,bases,attrs)

#Model
class Model(dict,metaclass=ModelMetaclass):
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)
    
    #增加 instance.key=value 的功能
    def __setattr__(self,key,value):
        self[key] = value

    #增加获取 instance.key 值的功能
    def __getattr__(self,key):
        try:
            return self[key]
        except:
            raise AttributeError('\'Model\' object has no attribution %s'%key)
    
    #获取key对应的value
    def getValue(self,key):
        return getattr(self,key,None)

    #获取key对应的value,若获取不到,选取字段的默认值
    def getValueOrDefault(self,key):
        value = getattr(self,key,None)
        if not value:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.info('Set field %s default value %s'%(key,value))
                setattr(self,key,value)
        return value

    #选出表格中所有记录
    @classmethod
    async def findnum(cls,selectField,where=None):
        sql = 'select %s from %s'%(selectField,cls.__table__)
        if where:
            sql ='%s where %s'%(sql,where)
        res = await select(sql)
        if len(res) == 0:
            return 
        return res

    #根据主键查询
    @classmethod
    async def find(cls,pk):
        sql = '%s where %s=?'%(cls.__select__,cls.__primary_key__)
        res = await select(sql,[pk],1)
        if len(res) == 0:
            return None
        return cls(**res[0])

    #全查询
    @classmethod
    async def findall(cls,selectField=None,where=None,args=None,**kw):
        if selectField:
            sql = 'select %s from %s'%(selectField,cls.__table__)
        else:
            sql = cls.__select__
        if where:
            sql = '%s where %s'%(sql,where)
        orderby = kw.get('orderby',None)
        if orderby is  not None:
            sql = '%s order by %s'%(sql,orderby)
        limit = kw.get('limit',None)
        if limit:
            if isinstance(limit,int):
                sql = '%s limit %s'%(sql,limit)
            elif isinstance(limit,tuple) and len(limit) == 2:
                sql = '%s limit %s,%s'%(sql,limit[0],limit[1])
            else:
                raise ValueError('Invalid limit value:%s'%limit)
        res = await select(sql,args)
        return [cls(**r) for r in res]

    #插入数据
    async def save(self):
        args = [self.getValueOrDefault(self.__primary_key__)]
        for item in map(self.getValueOrDefault,self.__fields__):
            args.append(item)
        sql = self.__insert__
        res = await execute(sql,args)
        if res != 1:
            logging.warn('failed to insert record: affected rows: %s'% rows) 
        else:
            logging.info('success to insert one record to %s'%self.__table__)

    #根据主键更新数据
    async def update(self,**kw):
        args = list(map(self.getValue,self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        res = await execute(self.__update__,args)
        if res != 1:
            logging.warn('failed to update record by primary key:%s'%self.getValue(self.__primary_key__)) 
        else:
            logging.warn('success to update record by primary key:%s'%self.getValue(self.__primary_key__))

    #根据主键删除数据
    async def remove(self,pk):
        sql = self.__delete__
        res = await execute(sql,[pk])
        if res != 1:
            logging.warn('failed to remove record by primary key:%s'%self.getValue(self.__primary_key__)) 
        else:
            logging.warn('success to remove record by primary key:%s'%self.getValue(self.__primary_key__))

