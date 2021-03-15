import logging
import ctypes
from typing import Any, Union, Optional, List, Tuple, Dict
import gi
from gi.repository import GLib


class GLibToPythonLogger:
    logger_prefix: str = ''
    logger_suffix: str = ''
    use_priority_field: bool = False

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
        fields: Dict[str, Union[str, bytes]] = {}
        for field in logfields:
            if field.length == 0:
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
                value = ctypes.c_byte * field.length
            fields[field.key] = value
        return fields

    def _get_logger_name(self, fields: dict) -> str:
        """Returns the appropiate logger name"""
        domain = fields.get('GLIB_DOMAIN', '')
        return self.logger_prefix \
            + domain.replace('-', '.') \
            + self.logger_suffix

    def _get_logger(self, fields: dict) -> logging.Logger:
        """Returns the appropiate logger"""
        return logging.getLogger(self._get_logger_name(fields))

    def _get_code_location(self, fields: dict) -> Tuple[Optional[str],
                                                        Optional[str],
                                                        Optional[str]]:
        """Returns an tuple describing the code location"""
        path_name = fields.get('CODE_PATH', None)
        line_no = fields.get('CODE_LINE', None)
        if line_no is not None:
            line_no = int(line_no)
        func_name = fields.get('CODE_FUNC', None)
        return (path_name, line_no, func_name)

    def _get_message(self, fields: dict) -> str:
        return fields.get('MESSAGE', '')

    _glib_level_map: Dict[GLib.LogLevelFlags, int] = {
        GLib.LogLevelFlags.LEVEL_ERROR: logging.ERROR,
        GLib.LogLevelFlags.LEVEL_CRITICAL: logging.CRITICAL,
        GLib.LogLevelFlags.LEVEL_WARNING: logging.WARNING,
        GLib.LogLevelFlags.LEVEL_MESSAGE: logging.INFO,
        GLib.LogLevelFlags.LEVEL_INFO: logging.INFO,
        GLib.LogLevelFlags.LEVEL_DEBUG: logging.DEBUG,
    }

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

    def _get_log_level(self, fields: dict, log_level: GLib.LogLevelFlags,
                       default=logging.INFO) -> int:
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
                         None  # sinfo/traceback
                         )
        record.glib_fields = fields
        return record

    def glibToPythonLogFunc(self, log_domain: str,
                            log_level: GLib.LogLevelFlags,
                            message: str, user_data: Any):
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
        The function GLib should call when writing. Used it with:
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
