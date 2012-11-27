"""
Utilities for making HTTP requests via Twisted's Agent.
"""

from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol


class BodyReceiver(Protocol):
    """
    Receive the body of an HTTP response
    """
    def __init__(self):
        self.finish = Deferred()
        self._buffer = []

    def dataReceived(self, data):
        """
        Store data in buffer
        """
        self._buffer.append(data)

    def connectionLost(self, reason):
        """
        Callback the ``finish`` ``Deferred`` with all the data that has
        been written to the buffer.
        """
        self.finish.callback(''.join(self._buffer))
