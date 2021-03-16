import logging
import uuid
from typing import Any, Dict, Optional, Callable
# from collections.abc import Callable
import gi
from gi.repository import GLib


logger = logging.getLogger(__name__)


class PythonToGLibLoggerHandler(logging.Handler):
    """
    Python logger handle that just forwards message records to the GLib logger.
    """

    replace_module_char: str = '-'
    """
    What to replace the dots (logger namespace separator) with when converting.
    """
    log_domain_prefix: str = ''
    """What it should put before the converted logger name."""
    log_domain_suffix: str = ''
    """What it should put after the converted logger name."""

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
        # Don't use the GLib equivalent because glib then likes to terminate.
        logging.CRITICAL: GLib.LogLevelFlags.LEVEL_WARNING,
        logging.ERROR: GLib.LogLevelFlags.LEVEL_WARNING,
        logging.WARNING: GLib.LogLevelFlags.LEVEL_WARNING,
        logging.INFO: GLib.LogLevelFlags.LEVEL_INFO,
        logging.DEBUG: GLib.LogLevelFlags.LEVEL_DEBUG,
        # Not used: GLib.LogLevelFlags.LEVEL_MESSAGE
    }
    """
    Map used to convert from a Python logger level to the GLib Log Level.
    """

    def _level_to_glib(self, level: int,
                       default: GLib.LogLevelFlags =
                       GLib.LogLevelFlags.LEVEL_DEBUG) -> GLib.LogLevelFlags:
        """
        Converts a Python loglevel to a GLib log level.
        If no mapping exists, use the specified default value.

        The default implementation will use the
        :py:data:`PythonToGLibLoggerHandler._level_to_glib_map`
        map.
        """
        for key in sorted(self._level_to_glib_map, reverse=True):
            if level >= key:
                return self._level_to_glib_map[key]
        return default

    def _get_log_domain(self, record: logging.LogRecord) -> str:
        """
        Returns the log domain for the specified record.
        The default implementation takes
        :py:data:`PythonToGLibLoggerHandler.log_domain_prefix`
        and
        :py:data:`PythonToGLibLoggerHandler.log_domain_prefix`
        into consideration.
        """
        return self.log_domain_prefix \
            + record.name.replace('.', self.replace_module_char) \
            + self.log_domain_suffix

    def _get_fields(self, record: logging.LogRecord,
                    update_from_record: bool = True) -> Dict[str, Any]:
        """
        Return fields to use based on the given log record.

        The default implementation will insert the following keys:

        * ``MESSAGE``: The formatted message
        * ``CODE_FUNC``, ``CODE_FILE``, ``CODE_LINE``: Where it logged
        * ``PYTHON_MESSAGE``: The unformatted message
        * ``PYTHON_MODULE``: What module the log was emitted from
        * ``PYTHON_LOGGER``: To what logger name it was supposed to log to
        * ``PYTHON_TNAME``: Thread Name
        * ``PYTHON_TID``: Thread ID

        The default implementaion will also insert exception information:

        * ``PYTHON_EXC``: Exception type with complete name
        * ``PYTHON_EXC_MESSAGE``: Stringify exception message

        Additionally, the default implementation will also insert (and
        override) values from the ``glib_fields`` attribute of the record,
        if it exists and is a :py:class:`dict`, when ``update_from_record``
        is ``True`` (the default).

        Subclasses can override this function to insert their own values
        and such.
        """
        fields = {
            'MESSAGE': self.format(record),
            'CODE_FUNC': record.funcName,
            'CODE_FILE': record.pathname,
            'CODE_LINE': record.lineno,
            'PYTHON_MESSAGE': record.getMessage(),
            'PYTHON_MODULE': record.module,
            'PYTHON_LOGGER': record.name,
            'PYTHON_TNAME': record.threadName,
            'PYTHON_TID': record.thread,
        }

        if record.exc_info is not None:
            exc_type, exc, exc_tb = record.exc_info
            if exc_type is None:
                exc_type = type(exc)
            type_name = exc_type.__module__ + '.' + exc_type.__qualname__
            fields['PYTHON_EXC'] = type_name
            fields['PYTHON_EXC_MESSAGE'] = str(exc)

        if hasattr(record, 'glib_fields') and update_from_record:
            if isinstance(getattr(record, 'glib_fields', None), dict):
                fields.update(getattr(record, 'glib_fields', {}))

        return fields

    def _convert_fields_dict(self, d: Dict[str, Any]
                             ) -> Dict[str, GLib.Variant]:
        """
        Modifies a dictionary of the fields to convert their values into GLib
        Variants, ready to be passed into :py:func:`GLib.log_variant`.

        By default, existing :py:class:`GLib.Variant` objects are untouched,
        strings are converted to :py:class:`Glib.Variant` strings,
        and :py:class:`bytes` objects to :py:class:`Glib.Variant` bytes,
        as per the official documentation.

        For other objects :py:func:`str` is called and the resulting string
        is inserted.

        Note that strings containing an null-byte will be cut off for that
        point. An warning will be emitted in that case.
        """
        for key, value in d.items():
            # TODO: What about keys that aren't strings?
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
        """
        Log the specified record, by converting and forwarding it to the
        GLib logging system.

        Normally, you wouldn't use this directly but rather implicitly via
        Pythons logging system.
        """
        log_domain = self._get_log_domain(record)
        log_level = self._level_to_glib(record.levelno)
        fields_dict = self._get_fields(record)
        if 'MESSAGE' not in fields_dict:
            logger.error("Missing mandatory MESSAGE, possible crash ahead: %r",
                         fields_dict)
        fields = GLib.Variant('a{sv}', self._convert_fields_dict(fields_dict))
        GLib.log_variant(log_domain, log_level, fields)


_GLib_LogWriterFunc = Callable[[GLib.LogLevelFlags, GLib.LogField, Any],
                               GLib.LogWriterOutput]


class PythonToGLibWriterHandler(PythonToGLibLoggerHandler):
    """
    Python logger handler that directly forwards to an glib logger writer
    function. Example::

        PythonToGLibWriterHandler(GLib.log_writer_default)

    Note that there are pre-existing instances at:

    - :py:data:`pythonToGLibWriterDefault` (uses :py:func:`GLib.log_writer_default`)
    - :py:data:`pythonToGLibWriterStandardStreams` (uses :py:func:`GLib.log_writer_standard_streams`)
    - :py:data:`pythonToGLibWriterJournald` (uses :py:func:`GLib.log_writer_journald`)
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
        Convert a record fields to an array of :py:class:`GLib.LogField`.
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
        """
        Log the specified record, by converting and forwarding it to the
        specified GLib Log Writer Function.

        Normally, you wouldn't use this directly but rather implicitly via
        Pythons logging system.
        """
        log_level = self._level_to_glib(record.levelno)
        fields = self._get_logfields(record)
        ret = self.writer(log_level, fields, self.user_data)
        return ret


pythonToGLibWriterDefault = \
    PythonToGLibWriterHandler(GLib.log_writer_default)
"""
Python Logger Handler to forward to :py:func:`GLib.log_writer_default`.
"""

pythonToGLibWriterStandardStreams = \
    PythonToGLibWriterHandler(GLib.log_writer_standard_streams)
"""
Python Logger Handler to forward to
:py:func:`GLib.log_writer_standard_streams`.
"""

pythonToGLibWriterJournald = \
    PythonToGLibWriterHandler(GLib.log_writer_journald)
"""
Python Logger Handler to forward to :py:func:`GLib.log_writer_journald`.
"""
