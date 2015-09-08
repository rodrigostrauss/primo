## Events ##
  * after\_attach
  * before\_start
  * after\_start
  * before\_start\_cancel
  * after\_start\_cancel

  * before\_kill
  * after\_kill
  * before\_kill\_cancel
  * after\_kill\_cancel

  * after\_crash


## Plugin ideas ##
```
StartTime time="03:00:00"
StdoutLog path="{log_path}"
StdinFrom type="file" path="{source_file}" <<-- send a file to the stdin
TcpMonitor port="6666" on_reject_actions="send_email,restart"
CrashMonitor on_crash="{self.Stdout.flush() ; self.Restart()}"


<Parameters>
 <Parameter name="tcp_port" value="6666">
</Parameters>

<Parameters source="params.xml" namespace="abc"/>

<GlobalOnEvent>
 <OnEvent event="after_crash" action="log.LogEvent(process.info)"/>
</GlobalEvents>

<Process id="xpto" path="{xpto_path}" bin="{xpto_bin}">
 <CommandLineAdd value="--input {tcp_port}"/>
 
 <OnEvent event="primo_start" action="{process.Start()}"/> <!-- starts on primo start -->
 
 <OnEvent event="after_crash" action="{process.Start()}" max_per_second="1"/>
 
 <OnEvent event="after_start" action="{log.LogInfo('xpto started: [%s] [%s]' % (self, event))}"/>
 
 <OnSpecificTime time="03:00:00" action="{process.Start()}"/>
 
 <EveryXSeconds interval="10" action="{ tcp.CheckPort(tcp_port) }" on_false="{self.Restart()}"/>

<!-- check for crash every second -->
<EveryXSeconds 
  interval="10" 
  condition="{ self.state == running }" 
  on_condition_true="{ process.Start() }"/>
 
</Process>

// starting process after another, can create a workflow this way
<Process id="to_be_run_after_xpto">
 <OnEvent event="xpto.after_stop" 
          condition="xpto.return_value == 0" 
      on_condition_true="{self.Start()}"
      on_condition_false=""
      on_condition_error=""
      />
      
      
 </Process>

// process search
<Process id="notepad" bin="notepad.exe">
 <OnEvent event="after_initialize" action="{ process.AttachByName() }"/>
</Process>
```


## use cases ##
  * process scheduling (OnSpecifiedTime)
  * kill a process (process.Kill())
  * monitor a process in a non-conventional way (checking for some open TCP port, for example) (via plugin)
  * plugins must be able to communicate with other plugins (probably enumerating process.plugins)
  * plugins must access a log object (something like primo.log)
  * stdout must be buffered by primo so plugins can access them even after the some other plugin has read it
  * there must be a way to create a global plugin list. The plugins in this list will be added to every process.
  * check if process is already running and attach to it. And have an option to launch only if not running
    * special action if there is more than one copy running
  * start and stop processes in specific time and rotate or backup files after stop