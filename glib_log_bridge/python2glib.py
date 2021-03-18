import logging
import ctypes
from typing import Any, Dict, Optional, Callable, List
# from collections.abc import Callable
import gi
from gi.repository import GLib


logger = logging.getLogger(__name__)


class LoggerHandler(logging.Handler):
    """
    Python logger handle that just forwards message records to the GLib logger.

    Note that since this subclasses :py:class:`logging.Handler`, view
    their documentation for more information, such as filters and so on.

    .. NOTE: Copy-Pasted from the __init__ version

    :param replace_module_char: What to replace the dots (logger namespace
        separator) with when converting.
        Also see :py:data:`LoggerHandler.replace_module_char`.
    :param log_domain_prefix: What it should put before the converted
        logger name.
        Also see :py:data:`LoggerHandler.log_domain_prefix`.
    :param log_domain_suffix: What it should put after the converted
        logger name.
        Also see :py:data:`LoggerHandler.log_domain_suffix`.
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
        """
        Initializes the instance, basically setting the formatter to ``None``
        and the filter list to empty.

        :param replace_module_char: What to replace the dots (logger namespace
            separator) with when converting.
            Also see :py:data:`LoggerHandler.replace_module_char`.
        :param log_domain_prefix: What it should put before the converted
            logger name.
            Also see :py:data:`LoggerHandler.log_domain_prefix`.
        :param log_domain_suffix: What it should put after the converted
            logger name.
            Also see :py:data:`LoggerHandler.log_domain_suffix`.
        """
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
        :py:data:`LoggerHandler._level_to_glib_map`
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
        :py:data:`LoggerHandler.log_domain_prefix`
        and
        :py:data:`LoggerHandler.log_domain_prefix`
        into consideration.

        :param record: The record to retrieve (and convert) the log domain
            from.
        :returns: The log domain name to use to log to GLib.
        """
        return self.log_domain_prefix \
            + record.name.replace('.', self.replace_module_char) \
            + self.log_domain_suffix

    def _get_fields(self, record: logging.LogRecord,
                    **kwargs) -> Dict[str, Any]:
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

        :param record: The record to convert into a suitable :py:class:`dict`.
        :param update_from_record: Extend it with ``record.glib_fields``,
            when it exists and is a :py:class:`dict`.
            Defaults to ``True``.
        :type update_from_record: bool
        :returns: Converted :py:class:`dict` from the specified record.
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

        if kwargs.get('update_from_record', True) and \
                hasattr(record, 'glib_fields') and \
                isinstance(getattr(record, 'glib_fields', None), dict):
            fields.update(getattr(record, 'glib_fields', {}))

        return fields

    def _convert_fields_dict(self, fields: Dict[str, Any]
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

        :param fields: The fields to convert.
        :returns: ``fields``, which has been modified to be converted to
            :py:class:`GLib.Variant`.
        """
        for key, value in fields.items():
            # TODO: What about keys that aren't strings?
            if isinstance(value, GLib.Variant):
                continue  # Already converted, ignore
            elif isinstance(value, bytes):
                fields[key] = GLib.Variant('ay', value)
            else:
                s = str(value)
                if '\x00' in s:
                    logger.warn("Found 0-byte in string, will be cut off: %r",
                                s)
                fields[key] = GLib.Variant('s', s)
        return fields

    def emit(self, record: logging.LogRecord):
        """
        Log the specified record, by converting and forwarding it to the
        GLib logging system.

        Normally, you wouldn't use this directly but rather implicitly via
        Pythons logging system.

        :param record: The record to log to GLib.
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


class GLibWriterHandler(LoggerHandler):
    """
    Python logger handler that directly forwards to an GLib logger writer
    function. Example::

        obj = GLibWriterHandler(GLib.log_writer_default)

    Note that there are pre-existing instances at:

    - :py:data:`GLibWriterHandlerDefault`
        (uses :py:func:`GLib.log_writer_default`)
    - :py:data:`GLibWriterHandlerStandardStreams`
        (uses :py:func:`GLib.log_writer_standard_streams`)
    - :py:data:`GLibWriterHandlerJournald`
        (uses :py:func:`GLib.log_writer_journald`)

    Note that since this subclasses :py:class:`logging.Handler`, view
    their documentation for more information, such as filters and so on.
    """
    def __init__(self, writer: _GLib_LogWriterFunc,
                 user_data: Any = None,
                 level=logging.NOTSET,
                 **kwargs):
        """
        Initializes the instance, basically setting the formatter to ``None``
        and the filter list to empty.

        :param writer: The writer function to forward to.
        :param user_data: Additional data to forward to the writer function.
        """
        super().__init__(level, **kwargs)
        self.writer: _GLib_LogWriterFunc = writer
        self.user_data: Any = user_data

    def _get_fields(self, record: logging.LogRecord,
                    **kwargs) -> Dict[str, Any]:
        """
        Return fields to use based on the given log record.

        See :py:func:`LoggerHandler._get_fields` for more
        information.

        This implementation will also set ``GLIB_DOMAIN`` when not set.

        :param record: The record to convert into a suitable :py:class:`dict`.
        :param update_from_record: Extend it with ``record.glib_fields``,
            when it exists and is a :py:class:`dict`.
            Defaults to ``True``.
        :type update_from_record: bool
        :returns: Converted :py:class:`dict` from the specified record.
        """
        fields = super()._get_fields(record, **kwargs)
        if 'GLIB_DOMAIN' not in fields:
            fields['GLIB_DOMAIN'] = self._get_log_domain(record)
        return fields

    def _convert_fields(self, fields: Dict[str, Any]) -> List[GLib.LogField]:
        """
        Convert a record fields to an list of :py:class:`GLib.LogField`.

        :param fields: The fields to convert.
        :returns: The converted fields.
        """
        log_fields: List[GLib.LogField] = []
        for key, value in fields.items():
            # TODO: Convert GLib Variants
            if isinstance(value, str):
                length = -1
                cvalue = ctypes.create_string_buffer(value.encode('utf-8'))
            else:
                if not isinstance(value, bytes):
                    value = str(value).encode('utf-8')
                length = len(value)
                cvalue = ctypes.create_string_buffer(value, len(value))
            log_field = GLib.LogField()
            log_field.key = key
            log_field.length = length
            log_field.value = ctypes.addressof(cvalue)
            # Keep cvalue buffer alive until after logging (using) it
            setattr(log_field, '_p2g_value_ctypes', cvalue)
            log_fields.append(log_field)
        return log_fields

    def _get_logfields(self, record: logging.LogRecord) -> List[GLib.LogField]:
        """
        Returns the :py:class:`GLib.LogField` to pass to GLib for the
        specified record.

        :param record: The record to convert from.
        :returns: The fields to pass to GLib.
        """
        return self._convert_fields(self._get_fields(record))

    def emit(self, record):
        """
        Log the specified record, by converting and forwarding it to the
        specified GLib Log Writer Function.

        Normally, you wouldn't use this directly but rather implicitly via
        Pythons logging system.

        :param record: The record to forward to GLib.
        """
        log_level = self._level_to_glib(record.levelno)
        fields = self._get_logfields(record)
        ret = self.writer(log_level, fields, self.user_data)
        return ret


GLibWriterHandlerDefault = GLibWriterHandler(GLib.log_writer_default)
"""
Python Logger Handler to forward to :py:func:`GLib.log_writer_default`.
"""

GLibWriterHandlerStandardStreams = \
    GLibWriterHandler(GLib.log_writer_standard_streams)
"""
Python Logger Handler to forward to
:py:func:`GLib.log_writer_standard_streams`.
"""

GLibWriterHandlerJournald = GLibWriterHandler(GLib.log_writer_journald)
"""
Python Logger Handler to forward to :py:func:`GLib.log_writer_journald`.
"""
