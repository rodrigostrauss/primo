import subprocess
import time
import os
import functools
from heapq import heappop, heappush


def path_join(a, *args):
    return os.path.join(a, *args)

class CancelEventException(object):
    def __init__(self, who, reason):
        pass

class PropertyParser(object):
     pass
    
class Process(object):
    def __init__(self, primo):
        self.bin = None
        self.path = None
        self.pid = None
        self.state = None
        self.properties = {}
        self.event_log = []
        self.command_line_parameters = []
        self.listeners = []

        #
        # TODO: stdin/stdout *should* be buffered so all plugins can
        # access it
        #
        self.process_obj = None
        self.primo = primo

    def add_listener(self, c):
        self.listeners.append(c)

    def StartNow(self):
        command_line = path_join(self.path, self.bin)
        params = ' '.join(self.command_line_parameters)

        self.primo.raise_process_event('before_start', self, 'after_start_cancel')

        self.process_obj = subprocess.Popen(self.command_line_parameters, executable=command_line)
        
        self.pid = self.process_obj.pid
        self.stdout = self.process_obj
        self.stdin = self.process_obj

        self.primo.post_process_event('after_start', self)

    def KillNow(self):
        self.primo.raise_process_event('before_kill', self, 'after_kill_cancel')

        self.process_obj.kill()
        
        self.primo.post_process_event('after_kill', self)

    def Start(self):
        return self.primo.schedule_callback(self.StartNow, 0)

    def Kill(self):
        return self.primo.schedule_callback(self.KillNow, 0)            

class ScheduleCallbackInfo(object):
    def __init__(self, when, callback):
        assert isinstance(when, float) # should be a timestamp like the returned by time.time()
        self.when = when
        self.callback = callback

    def __lt__(self, x):
        return self.when < x.when

    def __le__(self, x):
        return self.when <= x.when

    def __gt__(self, x):
        return self.when > x.when

    def __ge__(self, x):
        return self.when >= x.when

    def __repr__(self):
        t = time.localtime(self.when)
        # showing "callback=<functools.partial object at 0x010596C0>" will not be of much help...
        func = self.callback if not isinstance(self.callback, functools.partial) \
               else '%s %s' % (self.callback.func, self.callback.args)
        return '<ScheduleCallbackInfo: when=%02d:%02d:%02d, callback=%s>' % (t.tm_hour, t.tm_min, t.tm_sec, func)

class Primo(object):
    def __init__(self):
        self.processes = []
        self.properties = {}
        self.schedule = []
        self.global_listeners = []
        self.scheduling_log = False

    def add_global_listener(self, listener):
        self.global_listeners.append(listener)
        
    def add_process(self, process):
        self.processes.append(process)
        for c in self.global_listeners:
            process.add_listener(c)

    def schedule_callback(self, callback, delay):
        when = time.time() + delay
        info = ScheduleCallbackInfo(when, callback)

        if self.scheduling_log:
            print info
            
        heappush(self.schedule, info)
        return id(info)

    def post_global_event(self, event, delay = 0):
        return self.schedule_callback(
            functools.partial(self.raise_global_event, event),
            delay)

    def post_process_event(self, event, process, delay = 0):
        return self.schedule_callback(
            functools.partial(self.raise_process_event, event, process),
            delay)

    def post_event(self, event, process, callback, delay = 0):
        return self.schedule_callback(
            functools.partial(callback, event, self, process),
            delay)

    def post_timer_event(self, process, callback, delay):
        return self.post_event('timer', process, callback, delay)
        
    def raise_global_event(self, event, cancel_event = None):
        for p in self.processes:
            self.raise_process_event(event, p, cancel_event)
            
    def raise_process_event(self, event, process, cancel_event = None):
        '''
            listeners must accept three parameters: event, primo, process
        '''        
        for c in process.listeners:
            try:
                c(event, self, process)
            except CancelEventException, ex:
                if cancel_event:
                    try:
                        #
                        # it will not cause a stack overflow because this event can't be cancelled
                        # (hence can't generate more events)
                        #
                        self.raise_process_event(cancel_event, self, p)
                    except Exception, ex:
                        print 'unexpected exception calling cancel listeners: %s' % ex
                        
                    raise # reraise the exception after notifying the cancel
                else:
                    print 'callback "%s" is trying to cancel the event "%s", that can\'t be cancelled. Exception: %s' \
                          % (c, event, ex)
                
                
            except Exception, ex:
                print 'unexpected exception from callback "%s": %s' % (c, ex)
                
            
    def run(self):
        self.post_global_event('after_attach')

        max_sleep = 5        
        #
        # main loop. Main tasks:
        # * call schedule listeners. 
        #
        while 1:
            try:
                while self.schedule and self.schedule[0].when < time.time():
                    c = heappop(self.schedule)
                    try:
                        c.callback()
                    except Exception, ex:
                        print 'exception on main loop: %s' % (repr(ex),)
                    
                if not self.schedule:
                    time.sleep(max_sleep)
                    continue
                
                time_to_next = self.schedule[0].when - time.time()

                if time_to_next <= 0:
                    continue

                time_to_next = min( (time_to_next, max_sleep) )

                time.sleep(time_to_next)                
                
            except BaseException, ex:
                print 'exception on main loop: %s' % (repr(ex),)
                break

        #
        # MUST be a raise, we're already out of run loop
        #
        self.raise_global_event('before_detach')


def KillOnDetach(event, primo, process):
    if event == 'before_detach':
        process.KillNow()
        
def KeepRunningPlugin(event, primo, process):
    if event == 'after_finish':
        process.Start()

def AutoStartPlugin(event, primo, process):
    if event == 'after_attach':
        process.Start()

def LogEventsPlugin(event, primo, process):
    print 'process "%s", event="%s"' % (process.bin, event)

def FinishMonitorPlugin(event, primo, process):
    if event == 'after_start':
        primo.post_timer_event(process, FinishMonitorPlugin, 1) 
        return

    elif event == 'timer':
        if process.process_obj and not process.process_obj.poll() == None:
            primo.raise_process_event('after_finish', process)
            return

        primo.post_timer_event(process, FinishMonitorPlugin, 1)         

    
def Test():
    primo = Primo()
    p = Process(primo)

    primo.add_global_listener(AutoStartPlugin)
    primo.add_global_listener(LogEventsPlugin)
    primo.add_global_listener(FinishMonitorPlugin)

    p.add_listener(KeepRunningPlugin)
    p.add_listener(KillOnDetach)

    p.path = 'c:\\windows'
    p.bin = 'notepad.exe'

    primo.add_process(p)

    primo.run()

def main():
    Test()

if __name__ == '__main__':
    main()