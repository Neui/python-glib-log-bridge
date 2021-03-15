import logging
import uuid
from typing import Any, Dict, Optional, Callable
# from collections.abc import Callable
import gi
from gi.repository import GLib


logger = logging.getLogger(__name__)


class PythonToGLibLoggerHandler(logging.Handler):
    """
    Python logger handle that just forwards message records to the glib logger.
    """
    replace_module_char: str = '-'
    log_domain_prefix: str = ''
    log_domain_suffix: str = ''

    """An python logger handler that forwards to the GLib logging system"""
    def __init__(self, level=logging.NOTSET,
                 replace_module_char: str = replace_module_char,
                 log_domain_prefix: str = log_domain_prefix,
                 log_domain_suffix: str = log_domain_suffix,
                 ):
        super().__init__(level)
        self.replace_module_char = replace_module_char
        self.log_domain_prefix = log_domain_prefix
        self.log_domain_suffix = log_domain_suffix

    _level_to_glib_map: Dict[int, GLib.LogLevelFlags] = {
        logging.CRITICAL: GLib.LogLevelFlags.LEVEL_CRITICAL,
        logging.ERROR: GLib.LogLevelFlags.LEVEL_ERROR,
        logging.WARNING: GLib.LogLevelFlags.LEVEL_WARNING,
        logging.INFO: GLib.LogLevelFlags.LEVEL_INFO,
        logging.DEBUG: GLib.LogLevelFlags.LEVEL_DEBUG,
        # Not used: GLib.LogLevelFlags.LEVEL_MESSAGE
    }

    def _level_to_glib(self, level: int,
                       default: GLib.LogLevelFlags =
                       GLib.LogLevelFlags.LEVEL_DEBUG) -> GLib.LogLevelFlags:
        """Converts python loglevel to a GLib log level"""
        for key in sorted(self._level_to_glib_map, reverse=True):
            if level >= key:
                return self._level_to_glib_map[key]
        return default

    def _get_log_domain(self, record: logging.LogRecord) -> str:
        """Returns the log domain for the specified record"""
        return self.log_domain_prefix \
            + record.name.replace('.', self.replace_module_char) \
            + self.log_domain_suffix

    def _get_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Return fields to use based on the given log record"""
        fields = {
            'MESSAGE': self.format(record),
            'CODE_FUNC': record.funcName,
            'CODE_FILE': record.pathname,
            'CODE_LINE': record.lineno,
            'PYTHON_MESSAGE': record.getMessage(),
            'PYTHON_MODULE': record.module,
            'PYTHON_LOGGER': record.name,
            'PYTHON_THREADNAME': record.threadName,
            'TID': record.thread,  # TODO test
        }

        if record.exc_info is not None:
            exc_type, exc, exc_tb = record.exc_info
            if exc_type is None:
                exc_type = type(exc)
            type_name = exc_type.__module__ + '.' + exc_type.__qualname__
            fields['PYTHON_EXCEPTION'] = type_name
            fields['PYTHON_EXCEPTION_MESSAGE'] = str(exc)

        if hasattr(record, 'glib_fields'):
            if isinstance(record.glib_fields, dict):
                fields.update(record.glib_fields)

        return fields

    def _convert_fields_dict(self, d: Dict[str, Any]
                             ) -> Dict[str, GLib.Variant]:
        """Convert(/modify) a dictionary of the fields into GLib Variants"""
        for key, value in d.items():
            if isinstance(value, GLib.Variant):
                continue  # Already converted, ignore
            elif isinstance(value, bytes):
                d[key] = GLib.Variant('ay', value)
            else:
                s = str(value)
                if '\x00' in s:
                    logger.warn("Found 0-byte in string, will be cut off: %r",
                                s)
                d[key] = GLib.Variant('s', s)
        return d

    def emit(self, record: logging.LogRecord):
        log_domain = self._get_log_domain(record)
        log_level = self._level_to_glib(record.levelno)
        fields_dict = self._get_fields(record)
        fields = GLib.Variant('a{sv}', self._convert_fields_dict(fields_dict))
        GLib.log_variant(log_domain, log_level, fields)


# How to use:
# import logging
# logger = logging.getLogger()  # Logger to apply, this does for all messages
# handler = PythonToGLibLoggerHandler()
# logger.addHandler(handler)


_GLib_LogWriterFunc = Callable[[GLib.LogLevelFlags, GLib.LogField, Any],
                               GLib.LogWriterOutput]


class PythonToGLibWriterHandler(PythonToGLibLoggerHandler):
    """
    Python logger handler that directly forwards to an glib logger writer
    function. Example: PythonToGLibWriterHandler(GLib.log_writer_default)

    Note that there are pre-existing instances at:
    - pythonToGLibWriterDefault (with GLib.log_writer_default)
    - pythonToGLibWriterStandardStreams (with GLib.log_writer_standard_streams)
    - pythonToGLibWriterJournald (with GLib.log_writer_journald)
    """
    def __init__(self, writer: _GLib_LogWriterFunc,
                 user_data: Any = None,
                 level=logging.NOTSET,
                 **kwargs):
        super().__init__(level, **kwargs)
        self.writer: _GLib_LogWriterFunc = writer
        self.user_data: Any = user_data

    def _get_fields(self, record):
        fields = super()._get_fields(record)
        fields['GLIB_DOMAIN'] = self._get_log_domain()
        return fields

    def _convert_fields(self, d):
        """
        Convert a record fields to an array of GLib.LogField
        """
        fields = []
        for key, value in d:
            # TODO: Convert GLib Variants
            length = len(value)
            if isinstance(value, str):
                length = -1
            field = GLib.LogField(key=key, length=length, value=value)
            fields.append(field)
        return fields

    def _get_logfields(self, record):
        return self._convert_fields(self._get_fields(record))

    def emit(self, record):
        log_level = self._level_to_glib(record.levelno)
        fields = self._get_logfields(record)
        ret = self.writer(log_level, fields, self.user_data)
        return ret


"""Forward to GLib.log_writer_default"""
pythonToGLibWriterDefault = \
    PythonToGLibWriterHandler(GLib.log_writer_default)

"""Forward to GLib.log_writer_standard_streams"""
pythonToGLibWriterStandardStreams = \
    PythonToGLibWriterHandler(GLib.log_writer_standard_streams)

"""Forward to GLib.log_writer_journald"""
pythonToGLibWriterJournald = \
    PythonToGLibWriterHandler(GLib.log_writer_journald)
