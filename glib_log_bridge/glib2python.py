import logging
import ctypes
from typing import Any, Union, Optional, List, Tuple, Dict
import gi
from gi.repository import GLib


Fields = dict
FieldsType = Dict[str, Any]


class Logger:
    """
    Class that contains the state (and methods) used to
    accept logs from GLib and forward them to the python logging system.

    You need to pass the
    :py:func:`Logger.glibToPythonLogWriterFunc`
    to the :py:func:`GLib.log_set_writer_func`.
    The "user data" is ignored, but subclasses can take advantage of that if
    they somehow want to.

    Example usage:

    >>> g2plog = glib2python.Logger()
    >>> GLib.log_set_writer_func(g2plog.glibToPythonLogWriterFunc, None)

    You can create a subclass and overwrite the private methods if you need
    more control.

    .. NOTE: Copy-Pasted from the __init__ version

    :param logger_prefix: What it should put before the converted logger
        name. Also see :py:data:`Logger.logger_prefix`.
    :param logger_suffix: What it should put after the converted logger
        name. Also see :py:data:`Logger.logger_suffix`.
    :param use_priority_field: Force using the journald PRIORITY=-field
        rather than the log level GLib passes directly.
        Also see :py:data:`Logger.use_priority_field`.
    """

    logger_prefix: str = ''
    """What it should put before the converted logger name."""
    logger_suffix: str = ''
    """What it should put after the converted logger name."""
    use_priority_field: bool = False
    """
    Force using the journald PRIORITY=-field rather than the log level
    GLib passes directly.
    """

    def __init__(self,
                 logger_prefix: str = logger_prefix,
                 logger_suffix: str = logger_suffix,
                 use_priority_field: bool = use_priority_field
                 ):
        """
        Initialize itself by just setting the attributes.

        :param logger_prefix: What it should put before the converted logger
            name. Also see :py:data:`Logger.logger_prefix`.
        :param logger_suffix: What it should put after the converted logger
            name. Also see :py:data:`Logger.logger_suffix`.
        :param use_priority_field: Force using the journald PRIORITY=-field
            rather than the log level GLib passes directly.
            Also see :py:data:`Logger.use_priority_field`.
        """
        self.logger_prefix = logger_prefix
        self.logger_suffix = logger_suffix
        self.use_priority_field = use_priority_field

    def _fields_to_dict(self,
                        logfields: List[GLib.LogField]
                        ) -> FieldsType:
        """
        Converts a list of :py:class:`GLib.LogField` to a python dictionary.

        For fields whose length is ``-1`` this is being treated as a UTF-8
        :py:class:`strings<str>`, but if any error occur they'll be in a
        :py:class:`bytes`-object.

        For other fields it'll always be a bytes object.
        Note that when the :py:data:`GLib.LogField.value` or
        :py:data:`GLib.LogField.length` is ``0``, an empty :py:class:`bytes`
        object is being used.

        :param logfields: The fields to convert from
        :returns: An dictionary of the converted fields
        """
        fields: FieldsType = {}
        for field in logfields:
            if field.value == 0 or field.length == 0:
                # field.value == 0 should be impossible, but
                # lets rather be safe
                value: Union[str, bytes] = b''
            elif field.length == -1:
                raw_value = ctypes.c_char_p(field.value).value
                if raw_value is None:
                    value = ""
                else:
                    try:
                        value = raw_value.decode(errors="strict")
                    except UnicodeError:
                        value = raw_value  # Keep value as bytes object
            else:
                buffer_ctype = ctypes.c_byte * field.length
                value = bytes(buffer_ctype.from_address(field.value))
            fields[field.key] = value
        return fields

    def _get_logger_name(self, fields: FieldsType) -> str:
        """
        Returns the appropiate logger name from the fields.
        By default this uses (and converts) the ``GLIB_DOMAIN`` field.

        The default implementation also uses
        :py:data:`Logger.logger_prefix`
        and
        :py:data:`Logger.logger_suffix`.

        :param fields: The fields to make the decision from.
        :returns: The name of the logger to use.
        """
        domain = fields.get('GLIB_DOMAIN', '')
        if isinstance(domain, bytes):
            domain = domain.decode(errors='replace')
        return self.logger_prefix \
            + domain.replace('-', '.') \
            + self.logger_suffix

    def _get_logger(self, fields: FieldsType) -> logging.Logger:
        """
        Returns the appropiate logger.

        :param fields: The fields to make the decision from.
        :returns: The logger to use to log to it.
        """
        return logging.getLogger(self._get_logger_name(fields))

    def _get_code_location(self, fields: FieldsType) -> Tuple[Optional[str],
                                                              int,
                                                              Optional[str]]:
        """
        Returns an tuple describing the code location.

        :param fields: The fields to make the decision from.
        """
        path_name = fields.get('CODE_PATH', None)
        if isinstance(path_name, bytes):
            path_name = path_name.decode(errors='replace')
        line_no = int(fields.get('CODE_LINE', -1))
        func_name = fields.get('CODE_FUNC', None)
        if isinstance(func_name, bytes):
            func_name = func_name.decode(errors='replace')
        return (path_name, line_no, func_name)

    def _get_message(self, fields: Dict[str, Union[str, bytes]]) -> str:
        """
        Returns the message to be passed to the logger.
        By default this uses the ``MESSAGE`` field.
        For non-string ``MESSAGE``, it'll call :py:func:`str` on it,
        except for a :py:class:`bytes` object, where it will
        :py:func:`bytes.decode` it into a string, and replace invalid
        characters.

        :param fields: The fields to extract the code location info from.
        :returns: The code path(/module name), line and function name.
        """
        message = fields.get('MESSAGE', '')
        if isinstance(message, bytes):
            return message.decode(errors='replace')
        return str(message)

    _glib_level_map: Dict[GLib.LogLevelFlags, int] = {
        GLib.LogLevelFlags.LEVEL_ERROR: logging.ERROR,
        GLib.LogLevelFlags.LEVEL_CRITICAL: logging.CRITICAL,
        GLib.LogLevelFlags.LEVEL_WARNING: logging.WARNING,
        GLib.LogLevelFlags.LEVEL_MESSAGE: logging.INFO,
        GLib.LogLevelFlags.LEVEL_INFO: logging.INFO,
        GLib.LogLevelFlags.LEVEL_DEBUG: logging.DEBUG,
    }
    """Maps from GLibs logging levels to python logging levels."""

    _log_level_priority_map: Dict[str, int] = {
        "0": logging.CRITICAL,
        "1": logging.WARNING,
        "2": logging.CRITICAL,
        "3": logging.ERROR,
        "4": logging.CRITICAL,
        "5": logging.INFO,
        "6": logging.INFO,
        "7": logging.DEBUG
    }
    """
    Maps from
    `journald's PRIORITY=-field <https://www.freedesktop.org/software/systemd/man/systemd.journal-fields.html#PRIORITY=>`__
    to pythons default logging levels.
    """

    def _get_log_level(self, fields: Fields, log_level: GLib.LogLevelFlags,
                       default=logging.INFO) -> int:
        """
        Converts the log level from the fields (or the GLib passed one)
        to an log level appropiate for Pythons logging system.

        :param fields: The fields to make the decision from.
        :param log_level: GLib log level passed by GLib to the callback.
        :param default: What to use whenever it couldn't figure out.
        :returns: The log level to use for Pythons logging.
        """
        priority = fields.get('PRIORITY', None)
        if priority is not None and self.use_priority_field:
            if priority in self._log_level_priority_map:
                return self._log_level_priority_map[priority]

        # Fallback when priority invalid or doesn't exists
        log_level &= GLib.LogLevelFlags.LEVEL_MASK
        for key in sorted(self._glib_level_map, reverse=False):
            if key & log_level:
                return self._glib_level_map[key]

        return default

    def _get_record(self, log_level: GLib.LogLevelFlags,
                    fields: Dict[str, Any],
                    user_data) -> logging.LogRecord:
        """
        Converts from the fields into an :py:class:`logging.LogRecord`
        ready to be submitted to Pythons logging system.

        The default implementation also inserts the original fields dictionary
        as the ``glib_fields`` attribute on the resulting
        :py:class:`logging.LogRecord`.

        :param log_level: GLib log level passed by GLib to the callback.
        :param fields: The fields to make the decision from.
        :param user_data: User data passed by GLib callback, specified when
            setting up the writer on the GLib side.
        """
        message = self._get_message(fields)
        level = self._get_log_level(fields, log_level)
        logger_name = self._get_logger_name(fields)
        path_name, line_no, func_name = self._get_code_location(fields)
        factory = logging.getLogRecordFactory()
        record = factory(logger_name,
                         level,
                         path_name,
                         line_no,
                         message,
                         None,  # args
                         None,  # exc_info
                         func_name,
                         None,  # sinfo/traceback
                         glib_fields=fields
                         )
        return record

    def logFunc(self, log_domain: str,
                log_level: GLib.LogLevelFlags,
                message: str, user_data: Optional[Any]):
        """
        The function GLib should call handling an entry the unstructured
        way.
        Pass this to :py:func:`GLib.log_set_handler`.
        Note that the default handler forwards to the structured version
        when one isn't registered, so please use
        :py:func:`logWriterFunc` instead.
        Example::

            GLib.log_set_handler("domain", GLib.LogLevelFlags.LEVEL_WARNING,
                                 obj.logFunc, None)

        WARNING: Not tested yet.

        :param log_domain: In what domain it was logged to.
        :param log_level: What log level is being used.
        :param message: The message logged.
        :param user_data: Additional data, specified when setting up the
            writer on the GLib side.
            Not used in the default implementation.
        :returns: Nothing that should be used, since it is a ``void``.
        """
        fields = {
            'MESSAGE': message,
            'GLIB_DOMAIN': log_domain,
        }
        self.logWriterFunc(log_level, fields, len(fields),
                           user_data)

    def logWriterFunc(self, log_level: GLib.LogLevelFlags,
                      logfields: Union[List[GLib.LogField],
                                       Dict[str, Any]],
                      logfields_n: int,
                      user_data: Optional[Any]
                      ) -> GLib.LogWriterOutput:
        """
        The function GLib should call when writing.
        Pass this to :py:func:`GLib.log_set_writer_func`, which is used
        when doing structured logging.
        Example::

            GLib.log_set_writer_func(obj.logWriterFunc, None)

        :param log_level: GLib version of the log level.
        :param logfields: Fields that the logger has.
            Can also directly be an converted dictionary, when you need to
            directly call it for some reason.
        :param logfields_n: Number of fields, same as ``len(logfields)``.
        :param user_data: Additional data, specified when setting up the
            writer on the GLib side.
            Not used in the default implementation.
        :returns: Whenever it handled successfully.
            In case of an exception, it'll return as being unhandled.
        """
        try:
            if isinstance(logfields, dict):  # For the other wrapper
                fields = logfields
            else:
                fields = self._fields_to_dict(logfields)
            record = self._get_record(log_level, fields, user_data)
            self._get_logger(fields).handle(record)
        except Exception:
            return GLib.LogWriterOutput.UNHANDLED
        return GLib.LogWriterOutput.HANDLED
