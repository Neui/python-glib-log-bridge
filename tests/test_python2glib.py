import unittest
import logging
import logging.handlers
import queue
from gi.repository import GLib
import glib_log_bridge.python2glib as p2g
import glib_log_bridge.glib2python as g2p
from hypothesis import given, strategies


LOGGER_NAME = 'glibtest'
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(1)
q: queue.Queue = queue.Queue()


def queueLogWriterFunc(log_level: GLib.LogLevelFlags,
                       logfields, n_logfields: int,
                       user_data) -> GLib.LogWriterOutput:
    fields = g2p.Logger._fields_to_dict(None, logfields)
    q.put(fields, block=False, timeout=1)
    return GLib.LogWriterOutput.HANDLED


class Python2GLibTest(unittest.TestCase):
    handler = None

    def setUp(self):
        GLib.log_set_writer_func(queueLogWriterFunc, None)

    def tearDown(self):
        if self.handler is not None:
            logger.removeHandler(self.handler)

    @given(strategies.text(alphabet=strategies.characters(
        blacklist_categories=('C'), blacklist_characters='\x00'),
        min_size=1))
    def test_basic(self, msg):
        self.handler = p2g.LoggerHandler()
        logger.addHandler(self.handler)
        try:
            logger.info(msg)
            self.assertEqual(msg, q.get(timeout=1)['MESSAGE'])
            self.assertTrue(q.empty())
        finally:
            logger.removeHandler(self.handler)

    def test_custom_fields(self):
        self.handler = p2g.LoggerHandler()
        logger.addHandler(self.handler)
        try:
            o = queue.Queue()
            logger.info("test message", extra={
                'glib_fields': {
                    'text': 'test',
                    'bytes': b'te\x00st',
                    'object': o,
                    'none': None,  # Passing NULL is impossible, so str is ued
                }
            })
            rec = q.get(timeout=1)
            self.assertEqual('test', rec['text'])
            self.assertEqual(b'te\x00st', rec['bytes'])
            self.assertEqual(str(o), rec['object'])
            self.assertEqual(str(None), rec['none'])
            self.assertTrue(q.empty())
        finally:
            logger.removeHandler(self.handler)

    def test_exception_fields(self):
        self.handler = p2g.LoggerHandler()
        logger.addHandler(self.handler)
        try:
            raise SyntaxError("Some Exception Msg")
        except SyntaxError:
            logger.exception("Oh what?")
            rec = q.get(timeout=1)
            self.assertEqual("builtins.SyntaxError", rec['PYTHON_EXC'])
            self.assertEqual("Some Exception Msg", rec['PYTHON_EXC_MESSAGE'])
            self.assertTrue(q.empty())
        finally:
            logger.removeHandler(self.handler)


if __name__ == '__main__':
    unittest.main()
