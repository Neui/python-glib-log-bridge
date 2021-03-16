import logging
import ctypes
from typing import Any, Union, Optional, List, Tuple, Dict
import gi
from gi.repository import GLib


class GLibToPythonLogger:
    """
    Class that contains the state (and methods) used to
    accept logs from GLib and forward them to the python logging system.

    You need to pass the
    :py:func:`GLibToPythonLogger.glibToPythonLogWriterFunc`
    to the :py:func:`GLib.log_set_writer_func`.
    The "user data" is ignored, but subclasses can take advantage of that if
    they somehow want to.

    Example usage:

    >>> g2plog = glib2python.GLibToPythonLogger()
    >>> GLib.log_set_writer_func(g2plog.glibToPythonLogWriterFunc, None)

    You can create a subclass and overwrite the private methods if you need
    more control.
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
        self.logger_prefix = logger_prefix
        self.logger_suffix = logger_suffix
        self.use_priority_field = use_priority_field

    def _fields_to_dict(self,
                        logfields: List[GLib.LogField]
                        ) -> Dict[str, Union[str, bytes]]:
        """
        Converts a list of :py:class:`GLib.LogField` to a python dictionary.

        For fields whose length is ``-1`` this is being treated as a UTF-8
        :py:class:`strings<str>`, but if any error occur they'll be in a
        :py:class:`bytes`-object.

        For other fields it'll always be a bytes object.
        Note that when the :py:data:`GLib.LogField.value` or
        :py:data:`GLib.LogField.length` is ``0``, an empty :py:class:`bytes`
        object is being used.
        """
        fields: Dict[str, Union[str, bytes]] = {}
        for field in logfields:
            if field.value == 0 or field.length == 0:
                # field.value == 0 should be impossible, but
                # lets rather be safe
                value: Union[str, bytes] = b''
            elif field.length == -1:
                raw_value = ctypes.c_char_p(field.value).value
                if raw_value is None:
                    continue  # Ignore
                try:
                    value = raw_value.decode(errors="strict")
                except UnicodeError:
                    value = raw_value  # Keep value as bytes object
            else:
                value = bytes((ctypes.c_byte * field.length)
                              .from_address(field.value))
            fields[field.key] = value
        return fields

    def _get_logger_name(self, fields: dict) -> str:
        """
        Returns the appropiate logger name from the fields.
        By default this uses (and converts) the ``GLIB_DOMAIN`` field.

        The default implementation also uses
        :py:data:`GLibToPythonLogger.logger_prefix`
        and
        :py:data:`GLibToPythonLogger.logger_suffix`.
        """
        domain = fields.get('GLIB_DOMAIN', '')
        return self.logger_prefix \
            + domain.replace('-', '.') \
            + self.logger_suffix

    def _get_logger(self, fields: dict) -> logging.Logger:
        """
        Returns the appropiate logger.
        """
        return logging.getLogger(self._get_logger_name(fields))

    def _get_code_location(self, fields: dict) -> Tuple[Optional[str],
                                                        Optional[str],
                                                        Optional[str]]:
        """
        Returns an tuple describing the code location.
        """
        path_name = fields.get('CODE_PATH', None)
        line_no = fields.get('CODE_LINE', None)
        if line_no is not None:
            line_no = int(line_no)
        func_name = fields.get('CODE_FUNC', None)
        return (path_name, line_no, func_name)

    def _get_message(self, fields: dict) -> str:
        """
        Returns the message to be passed to the logger.
        By default this uses the ``MESSAGE`` field.
        """
        message = fields.get('MESSAGE', '')
        if isinstance(message, bytes):
            return message.decode(errors="replace")
        return message

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

    def _get_log_level(self, fields: dict, log_level: GLib.LogLevelFlags,
                       default=logging.INFO) -> int:
        """
        Converts the log level from the fields (or the GLib passed one)
        to an log level appropiate for Pythons logging system.
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

    def glibToPythonLogFunc(self, log_domain: str,
                            log_level: GLib.LogLevelFlags,
                            message: str, user_data: Any):
        """
        TODO.
        """
        fields = {
            'MESSAGE': message,
            'GLIB_DOMAIN': log_domain,
        }
        self.glibToPythonLogWriterFunc(log_level, fields, len(fields),
                                       user_data)

    def glibToPythonLogWriterFunc(self, log_level: GLib.LogLevelFlags,
                                  logfields: Union[List[GLib.LogField],
                                                   Dict[str, Any]],
                                  logfields_n: int,
                                  user_data) -> GLib.LogWriterOutput:
        """
        The function GLib should call when writing. Use it like this::

            GLib.log_set_writer_func(obj.glibToPythonLogWriterFunc, None)
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
