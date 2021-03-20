Usage
=====

This library allows you to forward logs from the python side to the GLib
side and the other way around.
You can even forward logs to Python but still use GLib writer functions, such
as forwarding to ``journald``.
Depending what you do, look at the correct chapter of what you want to do.



Forward GLib → Python
---------------------

To be written.

Quick usage::

   from gi.repository import GLib
   import glib_log_bridge.glib2python as glib2python
   g2plog = glib2python.Logger()
   GLib.log_set_writer_func(g2plog.logWriterFunc, None)

After importing, :py:class:`glib_log_bridge.glib2python.Logger` is being
instantiated, which accepts the log messages and forwards them to the
Python Logger.
The :py:func:`glib_log_bridge.glib2python.Logger.logWriterFunc` is the actual
writer function that is then passed to :py:func:`GLib.log_set_writer_func`
to actually receive the messages and forward them.
The userdata-parameter is ignored, so it can be anything, or simply ``None``.

Customizing
^^^^^^^^^^^

To be written.

Respect ``G_MESSAGES_DEBUG``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To be written.

The filter :py:class:`glib_log_bridge.glib2python.FilterGLibMessagesDebug`
respects the ``G_MESSAGES_DEBUG`` environment variable by only forwarding
debug messages if the logger names appears in them (space-separated, and
dash-separated "namespaces") or ``all`` has been specified.

.. seealso::
    `Running and debugging GLib Applications - Environment variables <https://developer.gnome.org/glib/stable/glib-running.html>`__

This can then be applied to an :py:class:`logging.Logger` or
:py:class:`logging.Handler` via the :py:func:`logging.Logger.addFilter`
or :py:func:`logging.Handler.addFilter` methods.

.. note::
    ``G_MESSAGES_DEBUG`` is being converted by replacing the dashes
    to dots, since dashes are used in the GLib world to separate namespaces,
    but dots in the Python world.

.. warning::
    Filters don't get propagated when applied to a logger
    (so filters for the root logger get ignored by the ``"GLib"``-logger).
    Because of that, better apply it to the handler instead.

.. warning::
    Since the filters need to get the debug messages, you should set the
    log level of the :py:class:`logging.Logger` and :py:class:`logging.Handler`
    to :py:data:`logging.DEBUG` or lower, so they can be processed by
    the filter.

Alternatively, instead of applying a filter, you can use
:py:func:`glib_log_bridge.glib2python.FilterGLibMessagesDebug.register_loggers`
which registers the filter as well as set the log level of all loggers
specified in ``G_MESSAGES_DEBUG`` (or just the root logger when ``all`` is
specified).
This as the feature that :py:func:`logging.Logger.isEnabledFor` will properly
work for :py:data:`logging.DEBUG`, which can be used to do some more costly
operations when debugging.



Forward Python → GLib
---------------------

To be written.

Quick usage::

   import logging
   import glib_log_bridge.python2glib as python2glib
   handler = python2glib.LoggerHandler()
   logging.getLogger().addHandler(handler)
   # Logger to apply, logger.getLogger() does it for all messages

After importing, an normal :py:class:`glib_log_bridge.python2glib.LoggerHandler`
is being instantiated, which accepts the log messages from a logger and forwards
them to GLib.
To register the handler, you need to use :py:func:`logging.Logger.addHandler`
method on a :py:class:`logging.Logger`.
You most likely want to use the root logger :py:func:`logging.getLogger`,
so all logs are forwarded.

Alternatively, you can forward a specific logger. Note that the full logger
name is being used and converted to GLib format (that uses dashes instead of
dots), so usually you don't need to do anything special if you just want to
forward one logger (such as only forward the logs done by the application
itself).

Customizing
^^^^^^^^^^^

To be written.

You can create a custom :py:class:`logging.Filter` and add them via
:py:class:`logging.Handler.addFilter` to the
:py:class:`glib_log_bridge.python2glib.LoggerHandler` if you want to determine
which exact messages should be forwarded.

Directly use a GLib writer/handler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The classes :py:class:`glib_log_bridge.python2glib.GLibWriterHandler` and
:py:class:`glib_log_bridge.python2glib.GLibLogHandler` are like
:py:class:`glib_log_bridge.python2glib.LoggerHandler`, but instead forward
to an GLib-compatible :py:data:`GLib.LogWriterFunc` or :py:data:`Glib.LogFunc`.
They accept the corresponding function (and userdata) as the parameters
when instantiating::

   glibWriterHandlerDefault = GLibWriterHandler(GLib.log_writer_default)

.. warning::
    :py:class:`glib_log_bridge.python2glib.GLibLogHandler` uses the old
    non-structured GLib logging API, which only accepts the log domain,
    log level and the message itself. Other fields/information are dropped
    silently.

    Instead please use
    :py:class:`glib_log_bridge.python2glib.GLibWriterHandler`,
    which uses the newer structured GLib logging API and thus does not
    drop the additional fields.

There are pre-existing instances using the default writers GLib provides:

- :py:data:`glib_log_bridge.python2glib.glibWriterHandlerDefault`
  (uses :py:func:`GLib.log_writer_default`)
- :py:data:`glib_log_bridge.python2glib.glibWriterHandlerStandardStreams`
  (uses :py:func:`GLib.log_writer_standard_streams`)
- :py:data:`glib_log_bridge.python2glib.glibWriterHandlerJournald`
  (uses :py:func:`GLib.log_writer_journald`)
- :py:data:`glib_log_bridge.python2glib.glibLogHandlerDefault`
  (uses :py:func:`GLib.log_default_handler`, not recommended as per the
  warning above)

For example, if you want to forward to ``jorunald``, you can do::

   logging.getLogger().addHandler(python2glib.glibWriterHandlerJournald)
