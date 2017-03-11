#!/usr/bin/env python

# JULEA - Flexible storage framework
# Copyright (C) 2010-2017 Michael Kuhn
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from waflib import Context, Utils
from waflib.Build import BuildContext

import os
import subprocess

APPNAME = 'julea'
VERSION = '0.2'

top = '.'
out = 'build'

# CentOS 7 has GLib 2.42
glib_version = '2.42'

def options (ctx):
	ctx.load('compiler_c')

	ctx.add_option('--debug', action='store_true', default=False, help='Enable debug mode')
	ctx.add_option('--sanitize', action='store_true', default=False, help='Enable sanitize mode')

	ctx.add_option('--mongodb', action='store', default='{0}/external/mongo-c-driver'.format(Context.run_dir), help='MongoDB driver prefix')
	ctx.add_option('--otf', action='store', default='{0}/external/otf'.format(Context.run_dir), help='OTF prefix')

	ctx.add_option('--jzfs', action='store', default=None, help='JZFS prefix')

	ctx.add_option('--leveldb', action='store', default=None, help='LevelDB prefix')

def configure (ctx):
	ctx.load('compiler_c')
	ctx.load('gnu_dirs')

	ctx.env.CFLAGS += ['-std=c11']
	ctx.env.CFLAGS += ['-fdiagnostics-color']
	ctx.env.CFLAGS += ['-Wpedantic', '-Wall', '-Wextra']
	ctx.env.CFLAGS += ['-Wc99-c11-compat']
	ctx.define('_POSIX_C_SOURCE', '200809L', quote=False)

	ctx.check_large_file()

	for program in ('mpicc',):
		ctx.find_program(
			program,
			var = program.upper(),
			mandatory = False
		)

	ctx.check_cc(
		lib = 'm',
		uselib_store = 'M'
	)

	for module in ('gio', 'glib', 'gmodule', 'gobject', 'gthread'):
		ctx.check_cfg(
			package = '{0}-2.0'.format(module),
			args = ['--cflags', '--libs', '{0}-2.0 >= {1}'.format(module, glib_version)],
			uselib_store = module.upper()
		)

	for module in ('bson', 'mongoc'):
		ctx.check_cfg(
			package = 'lib{0}-1.0'.format(module),
			args = ['--cflags', '--libs'],
			uselib_store = module.upper(),
			pkg_config_path = '{0}/lib/pkgconfig'.format(ctx.options.mongodb)
		)

	ctx.env.JULEA_FUSE = \
	ctx.check_cfg(
		package = 'fuse',
		args = ['--cflags', '--libs'],
		uselib_store = 'FUSE',
		mandatory = False
	)

	if ctx.env.MPICC:
		# MPI
		ctx.env.JULEA_MPI = \
		ctx.check_cc(
			header_name = 'mpi.h',
			lib = Utils.to_list(ctx.cmd_and_log([ctx.env.MPICC, '--showme:libs']).strip()),
			includes = Utils.to_list(ctx.cmd_and_log([ctx.env.MPICC, '--showme:incdirs']).strip()),
			libpath = Utils.to_list(ctx.cmd_and_log([ctx.env.MPICC, '--showme:libdirs']).strip()),
			rpath = Utils.to_list(ctx.cmd_and_log([ctx.env.MPICC, '--showme:libdirs']).strip()),
			uselib_store = 'MPI',
			define_name = 'HAVE_MPI'
		)

	if ctx.options.jzfs:
		# JZFS
		ctx.env.JULEA_JZFS = \
		ctx.check_cc(
			header_name = 'jzfs.h',
			lib = 'jzfs',
			use = ['GLIB'],
			includes = ['{0}/include/jzfs'.format(ctx.options.jzfs)],
			libpath = ['{0}/lib'.format(ctx.options.jzfs)],
			rpath = ['{0}/lib'.format(ctx.options.jzfs)],
			uselib_store = 'JZFS',
			define_name = 'HAVE_JZFS'
		)

	ctx.env.JULEA_LEVELDB = \
	ctx.check_cfg(
		package = 'leveldb',
		args = ['--cflags', '--libs'],
		uselib_store = 'LEVELDB',
		pkg_config_path = '{0}/lib/pkgconfig'.format(ctx.options.leveldb) if ctx.options.leveldb else None,
		mandatory = False
	)

	ctx.env.JULEA_LEXOS = \
	ctx.check_cfg(
		package = 'lexos',
		args = ['--cflags', '--libs'],
		uselib_store = 'LEXOS',
		mandatory = False
	)

	ctx.check_cc(
		header_name = 'otf.h',
		lib = 'open-trace-format',
		includes = ['{0}/include/open-trace-format'.format(ctx.options.otf)],
		libpath = ['{0}/lib'.format(ctx.options.otf)],
		rpath = ['{0}/lib'.format(ctx.options.otf)],
		uselib_store = 'OTF',
		define_name = 'HAVE_OTF',
		mandatory = False
	)

	# stat.st_mtim.tv_nsec
	ctx.check_cc(
		fragment = '''
		#define _POSIX_C_SOURCE 200809L

		#include <sys/types.h>
		#include <sys/stat.h>
		#include <unistd.h>

		int main (void)
		{
			struct stat stbuf;

			(void)stbuf.st_mtim.tv_nsec;

			return 0;
		}
		''',
		define_name = 'HAVE_STMTIM_TVNSEC',
		msg = 'Checking for stat.st_mtim.tv_nsec',
		mandatory = False
	)

	if ctx.options.sanitize:
		ctx.check_cc(
			cflags = '-fsanitize=address',
			ldflags = '-fsanitize=address',
			uselib_store = 'ASAN',
			mandatory = False
		)

		ctx.check_cc(
			cflags = '-fsanitize=undefined',
			ldflags = '-fsanitize=undefined',
			uselib_store = 'UBSAN',
			mandatory = False
		)

	if ctx.options.debug:
		ctx.env.CFLAGS += ['-Wno-missing-field-initializers', '-Wno-unused-parameter', '-Wold-style-definition', '-Wdeclaration-after-statement', '-Wmissing-declarations', '-Wmissing-prototypes', '-Wredundant-decls', '-Wmissing-noreturn', '-Wshadow', '-Wpointer-arith', '-Wcast-align', '-Wwrite-strings', '-Winline', '-Wformat-nonliteral', '-Wformat-security', '-Wswitch-enum', '-Wswitch-default', '-Winit-self', '-Wmissing-include-dirs', '-Wundef', '-Waggregate-return', '-Wmissing-format-attribute', '-Wnested-externs', '-Wstrict-prototypes']
		ctx.env.CFLAGS += ['-ggdb']

		ctx.define('G_DISABLE_DEPRECATED', 1)
		ctx.define('GLIB_VERSION_MIN_REQUIRED', 'GLIB_VERSION_{0}'.format(glib_version.replace('.', '_')), quote=False)
		ctx.define('GLIB_VERSION_MAX_ALLOWED', 'GLIB_VERSION_{0}'.format(glib_version.replace('.', '_')), quote=False)
	else:
		ctx.env.CFLAGS += ['-O2']

	if ctx.options.debug:
		# Context.out_dir is empty after the first configure
		out_dir = os.path.abspath(out)
		ctx.define('JULEA_BACKEND_PATH_BUILD', '{0}/backend'.format(out_dir))

	ctx.define('JULEA_BACKEND_PATH', Utils.subst_vars('${LIBDIR}/julea/backend', ctx.env))

	ctx.write_config_header('include/julea-config.h')

def build (ctx):
	# Headers
	ctx.install_files('${INCLUDEDIR}/julea', ctx.path.ant_glob('include/*.h', excl='include/*-internal.h'))

	# Trace library
#	ctx.shlib(
#		source = ['lib/jtrace.c'],
#		target = 'lib/jtrace',
#		use = ['GLIB', 'OTF'],
#		includes = ['include'],
#		install_path = '${LIBDIR}'
#	)

	use_julea_core = ['M', 'GLIB', 'ASAN'] # 'UBSAN'
	use_julea_lib = use_julea_core + ['GIO', 'GOBJECT', 'BSON', 'OTF']
	use_julea_backend = use_julea_core + ['GMODULE']

	# Library
	ctx.shlib(
		source = ctx.path.ant_glob('lib/**/*.c'),
		target = 'lib/julea',
		use = use_julea_lib,
		includes = ['include'],
		install_path = '${LIBDIR}'
	)

	# Library (internal)
	ctx.shlib(
		source = ctx.path.ant_glob('lib/**/*.c'),
		target = 'lib/julea-private',
		use = use_julea_lib,
		includes = ['include'],
		defines = ['J_ENABLE_INTERNAL'],
		install_path = '${LIBDIR}'
	)

	clients = ['item']

	for client in clients:
		ctx.shlib(
			source = ctx.path.ant_glob('client/{0}/**/*.c'.format(client)),
			target = 'lib/julea-client-{0}'.format(client),
			use = use_julea_lib + ['lib/julea-private'],
			includes = ['include'],
			defines = ['J_ENABLE_INTERNAL'],
			install_path = '${LIBDIR}'
		)

	# Tests
	ctx.program(
		source = ctx.path.ant_glob('test/*.c'),
		target = 'test/julea-test',
		use = use_julea_core + ['lib/julea-private', 'lib/julea-client-item'],
		includes = ['include'],
		defines = ['J_ENABLE_INTERNAL'],
		install_path = None
	)

	# Benchmark
	ctx.program(
		source = ctx.path.ant_glob('benchmark/*.c'),
		target = 'benchmark/julea-benchmark',
		use = use_julea_core + ['lib/julea-private', 'lib/julea-client-item'],
		includes = ['include'],
		defines = ['J_ENABLE_INTERNAL'],
		install_path = None
	)

	# Server
	ctx.program(
		source = ctx.path.ant_glob('server/*.c'),
		target = 'server/julea-server',
		use = use_julea_core + ['lib/julea-private', 'GIO', 'GMODULE', 'GOBJECT', 'GTHREAD'],
		includes = ['include'],
		defines = ['J_ENABLE_INTERNAL'],
		install_path = '${BINDIR}'
	)

	backends_client = ['mongodb']

	# Client backends
	for backend in backends_client:
		use_extra = []

		if backend == 'mongodb':
			use_extra = ['MONGOC']

		ctx.shlib(
			source = ['backend/client/{0}.c'.format(backend)],
			target = 'backend/client/{0}'.format(backend),
			use = use_julea_backend + ['lib/julea'] + use_extra,
			includes = ['include'],
			install_path = '${LIBDIR}/julea/backend/client'
		)

	backends_server = ['gio', 'null', 'posix']

	if ctx.env.JULEA_LEVELDB:
		backends_server.append('leveldb')

	if ctx.env.JULEA_JZFS and ctx.env.JULEA_LEVELDB:
		backends_server.append('jzfs')

	if ctx.env.JULEA_LEXOS and ctx.env.JULEA_LEVELDB:
		backends_server.append('lexos')

	# Server backends
	for backend in backends_server:
		use_extra = []

		if backend == 'gio':
			use_extra = ['GIO', 'GOBJECT']
		elif backend == 'leveldb':
			use_extra = ['LEVELDB']
		elif backend == 'jzfs':
			use_extra = ['JZFS', 'LEVELDB']
		elif backend == 'lexos':
			use_extra = ['LEXOS', 'LEVELDB']

		ctx.shlib(
			source = ['backend/server/{0}.c'.format(backend)],
			target = 'backend/server/{0}'.format(backend),
			use = use_julea_backend + ['lib/julea'] + use_extra,
			includes = ['include'],
			install_path = '${LIBDIR}/julea/backend/server'
		)

	# Command line
	ctx.program(
		source = ctx.path.ant_glob('cli/*.c'),
		target = 'cli/julea-cli',
		use = use_julea_core + ['lib/julea-private', 'lib/julea-client-item'],
		includes = ['include'],
		defines = ['J_ENABLE_INTERNAL'],
		install_path = '${BINDIR}'
	)

	# Tools
	for tool in ('config', 'statistics'):
		ctx.program(
			source = ['tools/{0}.c'.format(tool)],
			target = 'tools/julea-{0}'.format(tool),
			use = use_julea_core + ['lib/julea-private', 'GIO', 'GOBJECT'],
			includes = ['include'],
			defines = ['J_ENABLE_INTERNAL'],
			install_path = '${BINDIR}'
		)

	# FUSE
	if ctx.env.JULEA_FUSE:
		ctx.program(
			source = ctx.path.ant_glob('fuse/*.c'),
			target = 'fuse/julea-fuse',
			use = use_julea_core + ['lib/julea', 'lib/julea-client-item', 'FUSE'],
			includes = ['include'],
			install_path = '${BINDIR}'
		)

	# pkg-config
	ctx(
		features = 'subst',
		source = 'pkg-config/julea.pc.in',
		target = 'pkg-config/julea.pc',
		install_path = '${LIBDIR}/pkgconfig',
		APPNAME = APPNAME,
		VERSION = VERSION,
		INCLUDEDIR = Utils.subst_vars('${INCLUDEDIR}', ctx.env),
		LIBDIR = Utils.subst_vars('${LIBDIR}', ctx.env),
		GLIB_VERSION = glib_version
	)
