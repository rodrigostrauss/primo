import subprocess
import time
import os

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
        self.callbacks = []

        #
        # TODO: stdin/stdout *should* be buffered so all plugins can
        # access it
        #
        self.process_obj = None
        self.primo = primo

    def add_callback(self, c):
        self.callbacks.append(c)

    def Start(self):
        command_line = path_join(self.path, self.bin)
        params = ' '.join(self.command_line_parameters)

        self.primo.raise_process_event('before_start', self, 'after_start_cancel')

        self.process_obj = subprocess.Popen(self.command_line_parameters, executable=command_line)
        
        self.pid = self.process_obj.pid
        self.stdout = self.process_obj
        self.stdin = self.process_obj

        self.primo.raise_process_event('after_start', self)

    def Kill(self):
        self.primo.raise_process_event('before_kill', self, 'after_kill_cancel')

        self.process_obj.kill()
        
        self.primo.raise_process_event('after_kill', self)        
        

class Primo(object):
    def __init__(self):
        self.processes = []
        self.properties = {}
        self.schedule = []
        self.global_callbacks = []
        
    def add_process(self, process):
        self.processes.append(process)
        for c in self.global_callbacks:
            process.add_callback(c)

    def add_global_callback(self, callback):
        self.global_callbacks.append(callback)

    def raise_global_event(self, action, action_cancel_action = None):
        for p in self.processes:
            self.raise_process_event(action, p, action_cancel_action)
        
    def raise_process_event(self, action, process, action_cancel_action = None):
        '''
            callbacks must accept three parameters: action, primo, process
        '''        
        for c in process.callbacks:
            try:
                c(action, self, process)
            except CancelEventException, ex:
                if action_cancel_action:
                    try:
                        #
                        # it will not cause a stack overflow because this event can't be cancelled
                        # (hence can't generate more events)
                        #
                        self.raise_process_event(action_cancel_action, self, p)
                    except Exception, ex:
                        print 'unexpected exception calling cancel callbacks: %s' % ex
                        
                    raise # reraise the exception after notifying the cancel
                else:
                    print 'callback "%s" is trying to cancel the event "%s", that can\'t be cancelled. Exception: %s' \
                          % (c, action, ex)
                
                
            except Exception, ex:
                print 'unexpected exception from callback "%s": %s' % (c, ex)
                
            
    def run(self):
        self.raise_global_event('after_attach')

        #
        # main loop. Main tasks:
        # * call schedule callbacks. 
        #
        while 1:
            try:
                time.sleep(1)
                self.raise_global_event('timer')
            except BaseException, ex:
                print 'exception on main loop: %s' % (repr(ex),)
                break
                

        self.raise_global_event('after_detach')
                
    def call_me_again(self, interval_in_seconds):
        add_to_schedule()


def AutoStartPlugin(action, primo, process):
    if action == 'after_attach':
        process.Start()

def LogEventsPlugin(action, primo, process):
    if action == 'timer':
        return
    
    print 'process "%s", event="%s"' % (process.bin, action)

def FinishMonitorPlugin(action, primo, process):

    if action == 'after_start':
        process.properties['finish_notified'] = False
        return

    elif action == 'timer':
        if not process.process_obj:
            return

        # already notified, don't wanna a stack overflow
        if process.properties['finish_notified']:
            return
        
        if not process.process_obj.poll() == None:
            process.properties['finish_notified'] = True
            primo.raise_process_event('after_finish', process)
    

def Test():
    primo = Primo()
    p = Process(primo)

    primo.add_global_callback(AutoStartPlugin)
    primo.add_global_callback(LogEventsPlugin)
    primo.add_global_callback(FinishMonitorPlugin)

    p.path = 'c:\\windows'
    p.bin = 'notepad.exe'

    primo.add_process(p)

    primo.run()

def main():
    Test()

if __name__ == '__main__':
    main()