Python ↔ GLib logger bridge
===========================

This library allows you to redirect either from the [python logger facility][python-logger] to the [glib logging facility][glib-logger], or the other way around.

[python-logger]: https://docs.python.org/3/library/logging.html
[glib-logger]: https://developer.gnome.org/glib/stable/glib-Message-Logging.html

**NOTE: THIS IS STILL IN DEVELOPMENT! IT MIGHT NOT WORK CORRECTLY, AND THE INTERFACE CAN CHANGE!**

Quick Usage
-----------

Look at the documentation for more information, more examples and
the API reference.

### GLib → Python
```python
from gi.repository import GLib
import glib_log_bridge.glib2python as glib2python
g2plog = glib2python.Logger()
GLib.log_set_writer_func(g2plog.logWriterFunc, None)
```

### Python → GLib
```python
import logging
import glib_log_bridge.python2glib as python2glib
handler = python2glib.LoggerHandler()
logging.getLogger().addHandler(handler)
# Logger to apply, logger.getLogger() does it for all messages
```

