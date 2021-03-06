#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = "Alfredo Miranda <alfredocdmiranda@gmail.com>"
__description__ = ""

import sys
import os
import time
import atexit
from signal import SIGTERM


class Daemon(object):
    """
    A generic daemon class.

    Usage: subclass the Daemon class and override the run() method
    """
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """

        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #1 failed: {0} ({1})\n".format(e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #2 failed: {0} ({1})\n".format(e.errno, e.strerror))
            sys.exit(1)

        # write pidfile
        atexit.register(self.delpid)
        pid = str(os.getpid())
        with open(self.pidfile, 'w+') as f:
            f.write("{0}\n".format(pid))

    def delpid(self):
        """
        Delete process' PID file.
        """
        os.remove(self.pidfile)

    def start(self):
        """
        Starts daemon.
        """
        # Check for a pidfile to see if the daemon already runs
        try:
            with open(self.pidfile,'r') as f:
                pid = int(f.read().strip())
        except IOError as e:
            pid = None

        if pid:
            message = "pidfile {0} already exist. Daemon already running!\n".format(self.pidfile)
            sys.stderr.write(message)
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """
        Stops daemon.
        """
        # Get the pid from the pidfile
        try:
            with open(self.pidfile,'r') as f:
                pid = int(f.read().strip())
        except IOError:
            pid = None

        if not pid:
            message = "pidfile {0} does not exist. Daemon not running!\n".format(self.pidfile)
            sys.stderr.write(message)
            return # not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError as err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print(str(err))
                sys.exit(1)

    def restart(self):
        """
        Restarts daemon.
        """
        self.stop()
        self.start()

    def run(self):
        """
        You must override this method when you subclass Daemon. It will be called after the process has been
        daemonized by start() or restart().
        """
        pass
