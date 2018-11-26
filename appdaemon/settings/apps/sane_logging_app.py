"""
AppDaemon app mixin and python logging wrapper to add in sane logging.

This allows you to use ``self._log.(debug|info|warning|error|critical)`` as
regular Python logging library methods, including args/kwargs handling like
the normal logging library. It preserves the proper source information
(file/module/line) and also adds it to the log format. Finally, this wrapper
adds an event handler to allow you to dynamically cause DEBUG-level log
messages to be logged at INFO for a specific app via sending a specific event,
effectively allowing runtime debug log toggling for a single app (but not
any libraries used by it).

To use this, include SaneLoggingApp in your class's superclasses and call

    self._setup_logging(self.__class__.__name__)

at the beginning of its initialize() method. Once that is done, you can call
the normal logging methods on ``self._log``.

To toggle debugging, trigger a HASS event of type LOGWRAPPER_SET_DEBUG
with data of:

    {'app_class': 'ClassName', 'debug_value': True|False}

Enabling this will cause all DEBUG log messages in the ClassName app/class to
actually be logged at INFO level.
"""

import sys
import logging
import os
import appdaemon.plugins.hass.hassapi as hass

# _srcfile is used when walking the stack to check when we've got the first
# caller stack frame.
#
if hasattr(sys, 'frozen'):  #support for py2exe
    _srcfile = "logging%s__init__%s" % (os.sep, __file__[-4:])
elif __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


class SaneLoggingApp(object):

    def _setup_logging(self, app_class_name, debug_default):
        self._app_class_name = app_class_name
        self._log = LogWrapper(self.get_main_log(), debug_as_info=debug_default)
        self.listen_event(
            self._handle_log_wrapper_debug, event='LOGWRAPPER_SET_DEBUG'
        )
        format = "[%(levelname)s %(filename)s:%(lineno)s - " \
                 "%(name)s.%(funcName)s() ] %(message)s"
        formatter = logging.Formatter(fmt=format)
        self.get_main_log().handlers[0].setFormatter(formatter)
        if debug_default:
            self.get_main_log().handlers[0].setLevel(logging.DEBUG)

    def _handle_log_wrapper_debug(self, event_name, data, _):
        """
        event type: LOGWRAPPER_SET_DEBUG
        data: {'app_class': 'ClassName', 'debug_value': True|False}
        """
        self._log.info('Got LOGWRAPPER_SET_DEBUG event data=%s', data)
        if data.get('app_class', 'unknown') != self._app_class_name:
            self._log.debug(
                'Ignoring LOGWRAPPER_SET_DEBUG event for class: %s',
                data.get('app_class', 'unknown')
            )
            return
        val = data.get('debug_value', None)
        if val is not True and val is not False:
            self._log.error(
                'LOGWRAPPER_SET_DEBUG event has invalid debug_value: %s',
                val
            )
            return
        self._log.set_debug_as_info(val)
        if val is True:
            self._log.info('Debug-as-info logging enabled via event')
        else:
            self._log.info('Debug-as-info logging disabled via event')


class LogWrapper(object):
    """
    Thanks to https://stackoverflow.com/a/22091220/211734
    """

    def __init__(self, lgr, debug_as_info=False):
        self.logger = lgr
        self._debug_as_info = debug_as_info

    def set_debug_as_info(self, value):
        self._debug_as_info = value

    def debug(self, msg, *args, **kwargs):
        if self._debug_as_info:
            self._log(logging.INFO, msg, args, **kwargs)
            return
        if self.logger.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        if self.logger.isEnabledFor(logging.INFO):
            self._log(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        if self.logger.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs):
        if self.logger.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        if self.logger.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, msg, args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        """
        Log 'msg % args' with the integer severity 'level'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.log(level, "We have a %s", "mysterious problem", exc_info=1)
        """
        if not isinstance(level, int):
            if logging.raiseExceptions:
                raise TypeError("level must be an integer")
            else:
                return
        if self.logger.isEnabledFor(level):
            self._log(level, msg, args, **kwargs)

    def _log(self, level, msg, args, exc_info=None, extra=None):
        """
        Low-level logging routine which creates a LogRecord and then calls
        all the handlers of this logger to handle the record.
        """
        # Add wrapping functionality here.
        if _srcfile:
            # IronPython doesn't track Python frames, so findCaller throws an
            # exception on some versions of IronPython. We trap it here so that
            # IronPython can use logging.
            try:
                fn, lno, func = self._find_caller()
            except ValueError:
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        else:
            fn, lno, func = "(unknown file)", 0, "(unknown function)"
        if exc_info:
            if not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()
        record = self.logger.makeRecord(
            self.logger.name, level, fn, lno, msg, args, exc_info, func, extra)
        self.logger.handle(record)

    def _find_caller(self):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = logging.currentframe()
        # On some versions of IronPython, currentframe() returns None if
        # IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            rv = (co.co_filename, f.f_lineno, co.co_name)
            break
        return rv
