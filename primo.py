import subprocess 

class CancelEventException(object):
    def __init__(self, who, reason):
        pass

class PropertyParser(object):
     pass
    
class Process(object):
    def __init__(self):
        self.bin = None
        self.path = None
        self.pid = None
        self.state = None
        self.properties = []
        self.event_log = []
        self.command_line_parameters = []
        self.callbacks = []
        
        #
        # TODO: stdin/stdout *should* be buffered so all plugins can
        # access it
        #
        self.process_obj = None
        self.primo = None

    def Start(self):
        command_line = path_join(self.path, self.bin)
        params = ' '.join(self.command_line_parameters)

        self.primo.invoke_callbacks('before_start', self, 'after_start_cancel')

        self.process_obj = subprocess.Popen(self.command_line_parameters, executable=command_line)
        
        p.pid = self.process_obj.pid
        self.stdout = p.stdout
        self.stdin = p.stdin

        self.primo.invoke_callbacks('after_start', self)

    def Kill(self):
        self.primo.invoke_callbacks('before_kill', self, 'after_kill_cancel')

        self.process_obj.kill()
        
        self.primo.invoke_callbacks('after_kill', self)        
        

def Primo(object):
    def __init__(self):
        self.processes = []
        self.properties = {}
        self.schedule = []
        
    def add_process(process):
        self.processes.append(process)
        
    def invoke_callbacks(self, action, process, action_cancel_action = None):
        '''
            callbacks must accept three parameters: action, primo, process
        '''        
        for c in process.callbacks:
            try:
                c(action, self, p)
            except CancelEventException, ex:
                if action_cancel_action:
                    try:
                        #
                        # it will not cause a stack overflow because this event can't be cancelled
                        # (hence can't generate more events)
                        #
                        self.invoke_callbacks(action_cancel_action, self, p)
                    except:
                        pass
                        
                    raise # reraise the exception after notifying the cancel
                else:
                    pass # if it can't be cancelled, we will ignore the exception
                
            except:
                pass # todo: other kind of exception, we don't care and will ignore
            
    def run(self):
        for p in self.processes:
            self.invoke_callbacks('after_attach', p)
                 
        #
        # main loop. Main tasks:
        # * call schedule callbacks. 
        #
        while 1:
            # todo: check all processes health
            
            # todo: run schedules callbacks
            pass

        for p in self.processes:
            self.invoke_callbacks('after_detach', p)
            
                
    def call_me_again(self, interval_in_seconds):
        add_to_schedule()
        
            
    
class StartTime:
    def __init__(self, primo, **kargs):
        self.time = kargs['time']
        primo.advise()
    
    def on_event(self, primo, action, process):
        pass
        
    def after_action(self, primo, action, process):
         pass


def Test():
    primo = Primo()
    p = Process()

    p.path = 'c:\\windows'
    p.bin = 'notepad.exe'

    primo.add_process(p)

    primo.run()

    

def main():
    Test()


if __name__ == '__main__':
    main()
     
     