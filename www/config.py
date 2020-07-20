#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import config_default


#给字典类型添加 d.key 的属性
class Dict(dict):
    def __init__(self,keys=(),values=(),**kw):
        super(Dict,self).__init__(**kw)
        for k,v in zip(keys,values):
            self[k] = v

    def __setattr__(self,key,value):
        self[key] = value

    def __getattr__(self,key):
        try:
            return self[key]
        except:
            raise AttributeError('\'Dict\' has no Attribution %s'%key)

#对两个配置文件做merge，用override对default进行覆盖
def merge(default,override):
    config = dict()
    for k,v in default.items():
        if k in override:
            if isinstance(v,dict):
                config[k] = merge(v,override[k])
            else:
                config[k] = override[k]
        else:
            config[k] = v
    return config

#将普通dict类型转换成自定义的Dict类型
def toDict(d):
    D = Dict()
    for k,v in d.items():
        D[k] = toDict(v) if isinstance(v,dict) else v
    return D


configs = config_default.configs

try:
    import config_override
    configs = merge(configs,config_override.configs)
except:
    raise 

configs = toDict(configs)


