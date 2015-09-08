# Introduction #
Primo is a process manager. It uses a xml config file where you can specify actions to be executed on process events, like start and stop. Primo is made using pure Python, if you have Python installed, just download primo.py and you're good to go. It's tested on Windows and Linux (Ubuntu), but it will **probably** run flawlessly on MacOS and different GNU/Linux distributions.

# Details #
Primo reads an xml file that holds the configuration for a specific scenario. It includes all the processes that will be created and/or managed and all the listeners (more on this in a while).

The following config file will launch notepad, and stop primo when notepad is closed:

```xml
<?xml version="1.0"?>
<Primo>
 
 <Parameters>
  <ParameterFromEnvironment name="windows_path" varname="WINDIR"/>
 </Parameters>
 
 <Process path="{windows_path}" bin="notepad.exe" id="notepad">
  <AutoStart/>
  <EventHandler event="after_finish" action="{ primo.Stop() }"/>
 </Process>
 
</Primo>

```

Most of this config file seen pretty obvious. You can browse some example files on the tests directory. Lets dig a little bit more.

# Concepts #

Primo is the name of our process manager, that runs on Windows and Linux. It holds informations about all the processes it controls and about the global parameters those processes need to run.

## Parameters and Variable Expansion ##
Unless you have a very simple scenario (like start a single process using a hard-coded path), most information you will use to start and control processes will be parameters. From the binary path that can change between machines to the number of times a process will be restarted before giving up, using parameters will make you like easier.

```xml
<Parameters>
  <Parameter name="path" value="/usr/bin"/>
</Parameters>
```

This a simple "Parameters" section, creating just a simple parameter.

When you use {something} syntax, primo will eval "something" as a parameters, runtime variable or even code. Actually, you can use any valid python code that eval()'s to something. Examples:

```xml
<!-- read parameter from an environment variable and create a "windows_path" parameter -->
<ParameterFromEnvironment name="windows_path" varname="WINDIR"/>

<!-- compose a parameter from another parameter -->
<Parameter name="system32_path" value="{windows_path}\system32"/>

<!-- primo accepts python code. This yields 'aaaaa'. All parameter are available in the global scope -->
<Parameter name="xpto" value="{ 'a' * 5 }"/>

```

All expressions are evaluated when the XML tag is read. There's no lazy evaluation. If you want to change something during the process execution, you must use a listener (event handler) and change it using the action code. Parameters can be changed during primo lifetime.

## Process ##
It's an OS process, created by primo. You need to inform at least a path and a binary file name your OS will run (it includes `*`nix files with +x attribute). You can give an id to a process if you want to reference it in the future. The following primo config file will open the file win.ini using the notepad, even if user installed Windows in a different directory:

```xml
<?xml version="1.0"?>
<Primo>

 <Parameters>
  <ParameterFromEnvironment name="windows_path" varname="WINDIR"/>
  <Parameter name="txt_file" value="{windows_path}\win.ini"/>
 </Parameters>
 
 <Process path="{windows_path}" bin="notepad.exe" id="notepad">
  <CommandLineAdd value="{txt_file}"/>
  <AutoStart/> <!-- without this, notepad will not be started on primo start -->
 </Process>

</Primo>
```

The CommandLineAdd element can be added several times if you want. The "AutoStart" will start the process just after primo attaches to it.

## Actions ##
Some tags have an "action" attribute, that specifies a python code to run where that specific event happens. It's different from variable expansion, since it doesn't need to yield a value, it's just code. You can separate statements using a semicolon, just like any Python code. Although it's not recommended to add tons of code to an action element, it's up to you to abuse it or not.

```xml
<!-- Process will be started again when it finishes (or crashes) -->
<EventHandler event="after_finish" action="{ process.Start() }"/>

<!-- print process id after attach -->
<EventHandler event="after_start" action="{ print process.pid }"/>

<!-- create a pid file. "pid_file_name" is a parameter. All parameters are added to actions global scope -->
<EventHandler event="after_start" action="{ file(pid_file_name, 'w').write(process.pid) }"/>
```

Since you can only add one-liners, you don't need to care about code identation.

## Process Events ##
Event names follow the pattern (before|after)`_`(event name). When a listener handles an event that happens before something (before\_start, before\_kill), this listener can cancel this event. "After" type of event can't be cancelled (it already happened after all).

  * **after\_attach**: happens after primo runtime starts controlling this process. If you want to start some process just after primo knows about it, a "{process.Start()}" action will do the job (or a `<`AutoStart/`>`)
  * **before\_start**: happens before process start. You can cancel the process start at this point
  * **after\_start**: process is now running, you can now access its runtime properties. Things like "{process.pid}", or "{ process.running == True }"
  * **before\_kill**: process is about to be killed. You can cancel the kill now if you want
  * **after\_finish**: process is not running anymore. You can now access its return code.

## Timers ##
You can also use timers to run actions.

```xml

<?xml version="1.0"?>
<Primo>
 <Parameters>
  <Parameter name="windows_path" value="c:\windows"/>
  <Parameter name="system32_path" value="{windows_path}\system32"/>
  <Parameter name="txt_file" value="{system32_path}\eula.txt"/>
  <Parameter name="interval" value="2"/>
 </Parameters>
 
 <Process path="{windows_path}" bin="notepad.exe">
   <CommandLineAdd value="{txt_file}"/>
   <EachXSeconds interval="{interval}" action="{process.Start() if not process.running else process.Kill()}"/>
  <KillOnDetach/>
 </Process>
 
 <Process path="{windows_path}" bin="regedit.exe">
  <OnSpecificTime time="15:34:30" action="{process.Kill()}"/>
  <OnSpecificTime time="15:34:35" action="{process.Start()}"/>
  <OnSpecificTime time="15:34:36" action="{process.Kill()}"/>
 </Process>
</Primo>

```

In the above config file, notepad.exe will be started and stopped each 2 seconds. The form (True if condition else False) is the Python equivalent to C based languages' (condition ? True : False). So notepad.exe will blink each 2 seconds. The second process regedit.exe will be started and killed at specific time.


## Event Handlers ##
An event handler contains Python code to run when an event happens. You can register a process event handler or a global one, that will receive events from all process.

```xml
<?xml version="1.0"?>
<Primo>

 <GlobalListeners>
  <EventHandler event="before_dettach" action="{process.Stop()}"/>
  <EventHandler event="after_attach" action="{process.Start()}"/>
 </GlobalListeners>
 
 <Parameters>
  <Parameter name="windows_path" value="c:\windows"/>
  <Parameter name="system32_path" value="{windows_path}\system32"/>
  <Parameter name="txt_file" value="{system32_path}\eula.txt"/>
  <Parameter name="interval" value="2"/>
 </Parameters>
 
 <Process path="{windows_path}" bin="notepad.exe">
   <CommandLineAdd value="{txt_file}"/>
 </Process>

 <Process path="{windows_path}" bin="notepad.exe"/>

</Primo>

```

In example above, both copies of notepad will start on primo start, because there's a global event handler that will start the process on the "after\_attach" event.

## Standard Event Handlers ##
Some event handlers will be repeated in lots of config files. There's no point on having a process on the config file but never launching it. So, `<EventHandler event="after_attach" action="{process.Start()}"/>` should be present is most config files. Primo comes with lots of Standard Event Handlers:

  * AutoStart: equivalent to `<EventHandler event="after_attach" action="{process.Start()}"/>`
  * KillOnDetach: equivalent to `<EventHandler event="before_dettach" action="{process.Stop()}"/>`
  * EventLogger: this handler will respond to every event, and log it to stdout
  * AutoRestart: restart process on finish or crash. Like `<EventHandler event="atfer_stop" action="{process.Start()}"/>`
