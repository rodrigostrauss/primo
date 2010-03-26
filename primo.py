import subprocess
import time
import os
import sys
import functools
import traceback
import xml.sax
import datetime
import time
from heapq import heappop, heappush
from pprint import pprint


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
        # TODO: stdin/stdout *should* be buffered so all listeners can
        # access it
        #
        self.process_obj = None
        self.primo = primo

    def __repr__(self):
        return '<Process bin=%s>' % self.bin

    def add_listener(self, c):
        self.listeners.append(c)

    def StartNow(self):
        command_line = path_join(self.path, self.bin).encode(sys.getfilesystemencoding())
        
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

        
def warn_if_dying(meth):
    def new(*args, **kwargs):
        if args[0].dying: # assuming args[0] is the self param
            print 'WARNING: Not supposed to happen when primo is dying.', \
                'Callbacks scheduled when primo is dying will never be executed. Stack: \n"'
            traceback.print_list(traceback.extract_stack())
            
        return meth(*args, **kwargs)

    return new    
'''
class warn_if_dying(object):
    def __init__(self, x):
        self.x = x
    
    def __call__(self, *args, **kwargs):
        if args[0].dying: # assuming args[0] is a primo self
            print 'WARNING: action not supposed to happen when primo is dying: function="%s", params="%s"' \
              % (self.x, args)

        return self.x(*args, **kwargs)
'''

class Primo(object):
    def __init__(self):
        self.processes = []
        self.properties = {}
        self.schedule = []
        self.global_listeners = []
        self.scheduling_log = False
        self.dying = False
        self.initialize_global_listeners()

    def initialize_global_listeners(self):
        self.add_global_listener(FinishMonitorListener)

    #@warn_if_dying
    def add_global_listener(self, listener):
        self.global_listeners.append(listener)

    #@warn_if_dying    
    def add_process(self, process):
        self.processes.append(process)
        for c in self.global_listeners:
            process.add_listener(c)

    def schedule_callback_timestamp(self, callback, timestamp):
        info = ScheduleCallbackInfo(timestamp, callback)

        if self.scheduling_log:
            print info
            
        heappush(self.schedule, info)
        return id(info)
            
    def schedule_callback(self, callback, delay):
        timestamp = time.time() + delay
        return self.schedule_callback_timestamp(callback, timestamp)
        

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

    def post_event_timestamp(self, event, process, callback, timestamp):
        return self.schedule_callback_timestamp(
            functools.partial(callback, event, self, process),
            timestamp)

    def post_timer_event(self, process, callback, delay):
        return self.post_event('timer', process, callback, delay)

    def post_timer_event_timestamp(self, process, callback, timestamp):
        return self.post_event_timestamp('timer', process, callback, timestamp)    
        
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


        self.dying = True            

        #
        # MUST be a raise, we're already out of run loop
        #
        self.raise_global_event('before_detach')

'''
    Here for sake of history. You can do all this stuff using RunCodeOnEventListener

def KillOnDetach(event, primo, process):
    if event == 'before_detach':
        process.KillNow()
        
def KeepRunningListener(event, primo, process):
    if event == 'after_finish':
        process.Start()

def AutoStartListener(event, primo, process):
    if event == 'after_attach':
        process.Start()

def LogEventsListener(event, primo, process):
    print 'process "%s", event="%s"' % (process.bin, event)

'''

def FinishMonitorListener(event, primo, process):
    if event == 'after_start':
        primo.post_timer_event(process, FinishMonitorListener, 1) 
        return

    elif event == 'timer':
        if process.process_obj and not process.process_obj.poll() == None:
            primo.raise_process_event('after_finish', process)
            return

        primo.post_timer_event(process, FinishMonitorListener, 1)

class StringCodeAdapter(object):
    def __init__(self, string_code):
        self.func = compile(string_code, '<string>', 'exec')
        self.string_code = string_code
        
    def __call__(self, event, primo, process):
        globals = {'event': event, 'primo' : primo, 'process' : process, 'ret' : None}
        exec self.func in globals
        return globals['ret']

    def __repr__(self):
        return '<StringCodeAdapter string_code="%s">'% self.string_code

class ProcessMethodAdapter(object):
    def __init__(self, process_method):
        self.process_method = process_method
        
    def __call__(self, event, primo, process):
        self.process_method(process)

    def __repr__(self):
        return '<ProcessMethodAdapter method="%s">'% self.process_method

class RunCodeOnEventListener(object):
    def __init__(self, event_filter, func):
        self.func = func
        if isinstance(event_filter, basestring):
            self.event_filter = [str(event_filter)]
        else:
            self.event_filter = event_filter

    def __call__(self, event, primo, process):
        if not self.event_filter or event in self.event_filter:
            return self.func(event, primo, process)

    def __repr__(self):
        return '<RunCodeOnEventListener filter="%s", code="%s">'% (self.event_filter, self.func)

class OnSpecificTimeListener(object):
    def __init__(self, primo, process, time, action):
        time = datetime.datetime.strptime(time, '%H:%M:%S').time()
        d = datetime.datetime.now()

        # should schedule today or tomorrow?
        if time < d.time():
            d += datetime.timedelta(days=1)

        d = datetime.datetime.combine(d.date(), time)
        self.datetime = d

        #
        # the time parameter will shadow the time namespace, so we
        # need to import the function to avoid name collision. The parameter
        # be be named 'time' because it must be the same name used in the
        # xml tag: <OnSpecificTime time="17:30:00" action="{process.Start()}"
        # 
        from time import mktime        
        primo.schedule_callback_timestamp(self, mktime(d.timetuple()))

        action = action.strip(' {}')

        self.code = StringCodeAdapter(action)
        self.primo = primo
        self.process = process

    def __call__(self):
        print 'OnSpecificTime, callback="%s", datetime="%s"' % (self.code, self.datetime)
        self.code('timer', self.primo, self.process)


test_xml = \
'''
<Primo>
 <GlobalListeners>
  <EventLogger/>
  <KillOnDetach/>
 </GlobalListeners>
 
 <Process path="c:\windows" bin="notepad.exe">
  <OnEvent event="after_attach" action="{process.Start()}"/>
 </Process>
</Primo>
'''

class XmlConfigParser(xml.sax.handler.ContentHandler):
    def __init__(self):
        self.element_handlers = {}
        self.element_handlers['Primo'] = self._PrimoElement
        self.element_handlers['GlobalListeners'] = self._GlobalListenersElement
        self.element_handlers['Process'] = self._ProcessElement
        self.element_handlers['OnEvent'] = self._OnEventElement
        self.element_handlers['OnSpecificTime'] = self._OnSpecificTimeElement

        self.listeners = {}
        
        
        self.listeners['EventLogger'] = \
            lambda name, attrs: RunCodeOnEventListener(None,
                StringCodeAdapter('print \'process "%s", event="%s"\' % (process.bin, event)'))

        self.listeners['KillOnDetach'] = \
            lambda name, attrs: RunCodeOnEventListener('before_detach', ProcessMethodAdapter(Process.KillNow)) 
        
        self.context_stack = []

        self.primo = None

    def _push_current_handler(self):
        self._push_handler(self.context_stack[-1].handler)
                           
    def _push_handler(self, handler):
        class ElementHandlerInfo:
            pass

        eh = ElementHandlerInfo()
        eh.handler = handler
        self.context_stack.append(eh)
        return eh

    def _pop_handler(self):
        self.context_stack.pop(-1)

    def _call_current_handler(self, name, attrs):
        self.context_stack[-1].handler(name, attrs)

    #
    # Element handlers
    #
    def _PrimoElement(self, name, attrs):
        self._push_current_handler()

    def _OnSpecificTimeElement(self, name, attrs):
        process = getattr(self.context_stack[-1], 'process', None)
        return OnSpecificTimeListener(
            self.primo,
            process,
            **dict(zip([str(x) for x in attrs.keys()], attrs.values())))

    def _OnEventElement(self, name, attrs):
        event = attrs['event']
        action = attrs['action']
        action = action.strip('{}')
        return RunCodeOnEventListener(event, StringCodeAdapter(action))
        

    def _GlobalListenersElement(self, name, attrs):
        def add_global_listener(name, attrs):
            if name == 'OnEvent':
                listener = self._OnEventElement(name, attrs)
            else:
                listener = self.listeners[name](name, attrs)
                
            self.primo.add_global_listener(listener)

        self._push_handler(add_global_listener)

    def _ProcessElement(self, name, attrs):
        p = Process(self.primo)
        p.path = attrs['path']
        p.bin = attrs['bin']

        self.primo.add_process(p)

        def add_process_listener(name, attrs):
            if name == 'OnEvent':
                listener = self._OnEventElement(name, attrs)
            else:
                if name in self.listeners:
                    listener = self.listeners[name](name, attrs)
                else:
                    listener = None
                    self.element_handlers[name](name, attrs)
                    
            if listener:
                p.add_listener(listener)

        eh = self._push_handler(add_process_listener)
        eh.process = p

    def _SimpleElementRouter(self, name, attrs):
        self.element_handlers[name](name, attrs)

    def parse_file(self, file_name):
        xml.sax.parse(file_name, self)
        return self.primo        

    def parse_string(self, string):
        xml.sax.parseString(string, self)
        return self.primo

    #
    # SAX handlers
    #

    def startDocument(self):
        self.primo = Primo()
        self._push_handler(self._SimpleElementRouter)

    def endElement(self, name):
        #if self.context_stack[-1].pop_on_end:
        self._pop_handler()

    def _not_supposed_to_have_children(self, name, attrs):
        assert False
        
    def startElement(self, name, attrs):
        x = len(self.context_stack)
        
        self._call_current_handler(name, attrs)

        if len(self.context_stack) == x:        
            self._push_handler(self._not_supposed_to_have_children)

    
def Test():
    
    primo = Primo()
    p = Process(primo)

    primo.add_global_listener(FinishMonitorListener)    

    # auto start and relauch always
    primo.add_global_listener(
        RunCodeOnEventListener(['after_attach', 'after_finish'],
            ProcessMethodAdapter(Process.Start)))

    # log all events
    primo.add_global_listener(
        RunCodeOnEventListener(None,
            StringCodeAdapter('print \'process "%s", event="%s"\' % (process.bin, event)')))

    # kill on detach
    primo.add_global_listener(
        RunCodeOnEventListener('before_detach',
                             ProcessMethodAdapter(Process.KillNow)))

    p.path = 'c:\\windows'
    p.bin = 'notepad.exe'

    primo.add_process(p)

    primo.run()

def main():
    x = XmlConfigParser()
    primo = x.parse_file(sys.argv[1])

    for p in primo.processes:
        print pprint( (p, p.listeners) )

    print 'running...'
    primo.run()    

if __name__ == '__main__':
    main()