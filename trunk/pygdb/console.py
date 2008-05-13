#!/usr/bin/python

#
# Copyright (c) 2008 Michael Eddington
#
# Permission is hereby granted, free of charge, to any person obtaining a copy 
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights 
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell 
# copies of the Software, and to permit persons to whom the Software is 
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in	
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

# Authors:
#   Frank Laub (frank.laub@gmail.com)
#   Michael Eddington (mike@phed.org)

# $Id$


import sys
import os
import re
import pprint
from subprocess import *

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

"""
argv = (const char **) 0xbffff590
"""
VARIABLE_PATTERN = re.compile('([\S ]+) = ([\S ]+)')

GDB_PROMPT = '(gdb) '
GDB_CMDLINE = 'gdb -n -q'

class GdbConsole:
	def __init__(self):
		self.proc = Popen(GDB_CMDLINE , 0, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)

	def read_until_prompt(self):
		buf = ''
		while(True):
			ch = self.proc.stdout.read(1)
			if not ch:
				return buf

			buf += ch
			if len(buf) < len(GDB_PROMPT):
				continue

			if buf.endswith(GDB_PROMPT):
				outlen = len(buf) - len(GDB_PROMPT)
				return buf[:outlen]

	def send_cmd(self, cmd):
		cmd_line = cmd + '\n'
		self.proc.stdin.write(cmd_line)
		#sys.stdout.write('$ ' + cmd_line)

	def communicate(self, cmd):
		self.send_cmd(cmd)
		output = self.read_until_prompt()
		#sys.stdout.write(output)
		return output

class GdbThread:
	def __init__(self, gdb, txt):
		self.__gdb = gdb
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
		return self.__gdb.info_thread(self.num)

class GdbFrame:
	def __init__(self, gdb, txt):
		self.__gdb = gdb
		self._parse(txt)

	def _parse(self, txt):
		result = FRAME_PATTERN.match(txt)
		self.num = result.group('num')
		self.pc = result.group('pc')
		self.fun = result.group('fun')
		#self.args = result.group('args')
		self.source = result.group('src')

	def info(self):
		return self.__gdb.info_frame(self.num)

	def args(self):
		self.__gdb.select_frame(self.num)
		return self.__gdb.info_args()

	def locals(self):
		self.__gdb.select_frame(self.num)
		return self.__gdb.info_locals()

class GdbRegister:
	def __init__(self, gdb, txt):
		self.__gdb = gdb
		self._parse(txt)

	def _parse(self, txt):
		result = REGISTER_PATTERN.match(txt)
		self.name = result.group(1)
		self.hex_value = result.group(2)
		self.value = result.group(3)

class GdbVariable:
	def __init__(self, gdb, txt):
		self.__gdb = gdb
		self._parse(txt)

	def _parse(self, txt):
		result = VARIABLE_PATTERN.match(txt)
		self.name = result.group(1)
		self.value = result.group(2)

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
		self._process_run(txt)

	def signal(self): pass

	def start(self, args=None):
		txt = self._cmd('start', args)
		self._process_run(txt)

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

	def _process_run(self, txt):
		if txt.startswith('The program being debugged has been started already.'):
			txt = self._cmd('y')
		return txt

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

	def _parse_variables(self, txt):
		ret = {}
		for line in txt.splitlines():
			var = GdbVariable(self, line)
			ret[var.name] = var
		return ret

	def info_args(self):
		txt = self._cmd('info args')
		return self._parse_variables(txt)

	def info_address(self, symbol): pass
	def info_float(self): pass

	def info_frame(self, num):
		return self._cmd('info frame', num)

	def info_functions(self):
		return self._cmd('info functions')

	def info_locals(self):
		txt = self._cmd('info locals')
		return self._parse_variables(txt)

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
	gdb.file('qi')
	gdb.start()

	threads = gdb.info_threads().values()
	for thread in threads:
		print thread.info()

	gdb.step(3)

	stack = gdb.backtrace().values()
	for frame in stack:
		print frame.fun
		for local in frame.locals().values():
			print local.name + ': ' + local.value
		print

	all = gdb.info_registers().values()
	for reg in all:
		print reg.name + ' = ' + reg.hex_value + ' ' + reg.value

	gdb.quit()

except Exception, ex:
	print ex.message
