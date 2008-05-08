#!/usr/bin/python

import sys
import os
import re
from GdbConsole import GdbConsole

"""
0x6840 in
"""
PC_PATTERN = '(?:(?P<pc>0x[\dA-Fa-f]+) in )?'

"""
expand_token
[recv message]
"""
FUN_PATTERN = '(?P<fun>[\S ]+)'

"""
(argc=1, argv=0xbffff590)
()
"""
ARGS_PATTERN = '\((?P<args>[\S ]*)\)'

"""
at main.c:75
"""
SRC_PATTERN = '(?:\s+at\s+(?P<src>\S+))?'

"""
main (argc=1, argv=0xbffff590) at main.c:75
0x6840 in expand_token (obs=0x0, t=177664, td=0xf7fffb08) at macro.c:71
"""
LOCATION_PATTERN = PC_PATTERN + FUN_PATTERN + ' ' + ARGS_PATTERN + SRC_PATTERN

"""
* 1 process 2332 thread 0x20b  0x950aa9e6 in mach_msg_trap ()
* 1 process 3197 local thread 0x2d03  main (argc=1, argv=0xbffff590) at main.c:75
"""
INFO_THREAD_PATTERN = re.compile('(?P<cur>\*)?\s+(?P<num>\d+) process (?P<pid>\d+).+thread (?P<tid>0x[\dA-Fa-f]+)\s+' + LOCATION_PATTERN)

"""
#2  0x6840 in expand_token (obs=0x0, t=177664, td=0xf7fffb08)
    at macro.c:71
"""
FRAME_PATTERN = re.compile('\#(?P<num>\d+)\s+' + LOCATION_PATTERN)

"""
eip            0x950aa9e6	0x950aa9e6 <mach_msg_trap+10>
"""
REGISTER_PATTERN = re.compile('(\S+)\s+(0x[\dA-Fa-f]+)\s+(\S+)')

class GdbThread:
	def __init__(self, gdb, txt):
		self.gdb = gdb
		self._parse(txt)

	def _parse(self, line):
		result = INFO_THREAD_PATTERN.match(line)
		self.is_cur = result.group('cur') == '*'
		self.num = int(result.group('num'))
		self.pid = int(result.group('pid'))
		self.tid = result.group('tid')
		self.pc = result.group('pc')
		self.fun = result.group('fun')
		self.args = result.group('args')
		self.source = result.group('src')

	def info(self):
		return self.gdb.info_thread(self.num)

class GdbFrame:
	def __init__(self, gdb, txt):
		self.gdb = gdb
		self._parse(txt)

	def _parse(self, txt):
		result = FRAME_PATTERN.match(txt)
		self.num = result.group('num')
		self.pc = result.group('pc')
		self.fun = result.group('fun')
		self.args = result.group('args')
		self.source = result.group('src')

	def info(self):
		return self.gdb.info_frame(self.num)

class GdbRegister:
	def __init__(self, gdb, txt):
		self.gdb = gdb
		self._parse(txt)

	def _parse(self, txt):
		result = REGISTER_PATTERN.match(txt)
		self.name = result.group(1)
		self.hex_value = result.group(2)
		self.value = result.group(3)

class Gdb:
	def __init__(self):
		self.console = GdbConsole()
		self.console.read_until_prompt()

	def _cmd(self, cmd, args=None):
		if args:
			if args is list:
				args = ' '.join(args)
			else:
				args = str(args)
			cmd = cmd + ' ' + args
		return self.console.communicate(cmd)

	def file(self, filename):
		return self._cmd('file', filename)

	def quit(self):
		self.console.send_cmd('q')

	def help(self):
		return self._cmd('h')

####################################################
	# target
	def target_core(self, filename):
		return self._cmd('target core', filename)

	def target_exec(self, filename):
		return self._cmd('target exec', filename)

####################################################
	# frame
	def backtrace(self):
		ret = {}
		txt = self._cmd('backtrace')
		if txt.startswith('No stack.'):
			return ret

		for line in txt.splitlines():
			frame = GdbFrame(self, line)
			ret[frame.num] = frame
		return ret

	def down(self, count=None):
		txt = self._cmd('down', count)
		if txt.startswith('Bottom'):
			return None
		return GdbFrame(self, txt)

	def frame(self, frame=None):
		txt = self._cmd('frame', frame)
		return GdbFrame(self, txt)

	def return_(self, value=None):
		confirm = self._cmd('return', value)
		txt = self._cmd('y')
		return GdbFrame(self, txt)

	def select_frame(self, frame):
		self._cmd('select-frame', frame)

	def up(self, count=None):
		txt = self._cmd('up', count)
		if txt.startswith('Initial'):
			return None
		return GdbFrame(self, txt)

####################################################
	# data
	def delete_mem(self, num): pass
	def disable_mem(self, num): pass
	def disassemble(self, start=None, finish=None): pass
#	def dump(self): pass
	def enable_mem(self, num): pass
	def mem(self, lo, hi, mode=None, width=None, cache=None): pass
	def print_(self, exp, fmt=None): pass
	def printf(self, fmt, args): pass
	def ptype(self, exp): pass
	def set(self, var, exp): pass
	def whatis(self, exp): pass
	def x(self, address, fmt=None): pass

####################################################
	# running
	def attach(self, args):
		txt = self._cmd('attach', args)
		if txt.startswith('Unable'):
			raise Exception(txt)

		lines = txt.splitlines()
		if lines[1].startswith('Unable'):
			raise Exception(lines[1])
		return txt

	def continue_(self, ignore_count=None):
		return self._cmd('continue', ignore_count)

	def detach(self):
		return self._cmd('detach')

	def disconnect(self): pass

	def finish(self):
		"""step out"""
		pass

	def handle(self): pass
	def interrupt(self): pass
	def jump(self):
		return self._cmd('jump')

	def kill(self):
		txt = self._cmd('kill')
		if txt.startswith('The program is not being run.'):
			return
		return self._cmd('y')

	def next(self, count=None):
		"""step over"""
		return self._cmd('next', count)

	def nexti(self, count=None):
		return self._cmd('nexti', count)

	def run(self, args=None):
		txt = self._cmd('run', args)
		if txt.startswith('The program being debugged has been started already.'):
			txt = self._cmd('y')
		return txt

	def signal(self): pass

	def start(self, args=None):
		txt = self._cmd('start', args)
		if txt.startswith('The program being debugged has been started already.'):
			txt = self._cmd('y')
		return txt

	def step(self, count=None):
		"""step into"""
		return self._cmd('step', count)

	def stepi(self, count=None):
		return self._cmd('stepi', count)

	def thread(self, num):
		return self._cmd('thread', num)

	def thread_resume(self):
		return self._cmd('thread resume')

	def thread_suspend(self):
		return self._cmd('thread suspend')

	def until(self, location=None):
		return self._cmd('until', location)

####################################################
	# breakpoints
	def break_(self, location=None):
		return self._cmd('break', location)

	def catch(self):
		return self._cmd('catch')

	def clear(self):
		return self._cmd('clear')

	def condition(self):
		return self._cmd('condition')

	def delete(self):
		return self._cmd('delete')

	def disable(self):
		return self._cmd('disable')

	def enable(self):
		return self._cmd('enable')

	def watch(self):
		return self._cmd('watch')

####################################################
	# info
	def info_breakpoints(self):	pass
#	def info_all_registers(self): pass
	def info_args(self): pass
	def info_address(self, symbol): pass
	def info_float(self): pass

	def info_frame(self, num):
		return self._cmd('info frame', num)

	def info_functions(self): pass
	def info_locals(self): pass
	def info_mem(self): pass
	def info_pid(self): pass
	def info_program(self): pass
	def info_registers(self, reg=None):
		ret = {}
		txt = self._cmd('info registers', reg)
		if 'no registers' in txt:
			return ret

		lines = txt.splitlines()
		if len(lines) == 1:
			return GdbRegister(self, txt)

		for line in lines:
			reg = GdbRegister(self, line)
			ret[reg.name] = reg
		return ret

	def info_scope(self): pass
	def info_source(self): pass
	def info_sources(self): pass
	def info_stack(self): pass
	def info_symbol(self): pass
	def info_task(self): pass

	def info_thread(self, num):
		return self._cmd('info thread', num)

	def info_threads(self):
		ret = {}
		txt = self._cmd('info threads')
		if txt.startswith('No registers.'):
			return ret

		for line in txt.splitlines():
			thread = GdbThread(self, line)
			ret[thread.num] = thread
		return ret

	def info_types(self): pass
	def info_variables(self): pass
	def info_vector(self): pass


try:
	gdb = Gdb()
	gdb.file('/Users/franklaub/bin/qi')
	gdb.start()

	threads = gdb.info_threads().values()
	for thread in threads:
		print thread.info()

	stack = gdb.backtrace().values()
	for frame in stack:
		print frame.fun

	all = gdb.info_registers().values()
	for reg in all:
		print reg.name + ' = ' + reg.hex_value + ' ' + reg.value

	gdb.detach()
	gdb.quit()

except Exception, ex:
	print ex.message
