#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os,time,subprocess,sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def log(s):
    print('[Monitor]:%s'%s)

#重启操作文件的信息
command = ['echo','ok']
process = None

#结束进程
def kill_process():
    global process
    log('kill process [%s]...'%process.pid)
    process.kill()
    process.wait()
    log('process ended with code %s.'%process.returncode)
    process = None

#开启进程
def start_process():
    global process,command
    log('start process %s...'%' '.join(command))
    process = subprocess.Popen(command,stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr)

#重启进程
def restart_process():
    kill_process()
    start_process()

class MyFileSystemEventHander(FileSystemEventHandler):
    def __init__(self,fn):
        super(MyFileSystemEventHander,self).__init__(fn)
        self.restart = fn    #导入重启函数

    def on_any_event(self,event):
        if event.src_path.endwith('.py'):   #监视以 '.py' 结尾的文件
            log('Python source file changed: %s'%event.src_path)
            self.restart()
        
#监视
def start_watch(path,callback):
    observer = Observer()
    observer.schedule(MyFileSystemEventHander(restart_process),path,recursice=True)
    observer.start()
    log('wathcing directory %s ...'%path)
    start_process()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    argv = sys.argv[1:]
    if not argv:
        print('Usage: ./pymonitor your-script.py')
        exit(0)
    if argv[0] != 'python3':
        argv.insert(0, 'python3')
    command = argv
    path = os.path.abspath('.')
    start_watch(path, None)
    

