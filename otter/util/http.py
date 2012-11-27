"""
Utilities for making HTTP requests via Twisted's Agent.
"""
from collections import namedtuple
from cStringIO import StringIO

from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import FileBodyProducer
from twisted.web.http import Headers, NO_BODY_CODES


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


ResponseWrapper = namedtuple('ResponseWrapper', ['response', 'content'])


def request(agent, method, url, headers=None, body=None):
    """
    Convenience function for making a request with agent and automatically
    calling `deliverBody` on the response if there is a body.

    :param agent: the agent to use to make the request
    :type agent: ``twisted.web.client.Agent``

    :param method: the http method
    :type method: ``str``

    :param url: the url to which to make the request
    :type url: ``str``

    :param headers: the headers to pass in the request - defaults to no
        headers
    :type headers: ``dict`` of ``lists`` or ``None``

    :param body_json: the JSON blob to pass as a body in a POST request -
        defaults to no body
    :type request_body: JSON-compatible ``dict`` or ``list``, or ``None``

    :return: a named tuple that contains the response from the request
        as well as the content in string form.
    :rtype: ``ResponseWrapper``
    """
    if headers is not None:
        headers = Headers(headers)
    if body is not None:
        body = FileBodyProducer(StringIO(body))

    body_receiver = BodyReceiver()

    def deliver_body(response):
        if int(response.code) in NO_BODY_CODES:
            # If the response code is one of these codes, there is no
            # body and if deliverBody is called with the body receiver,
            # the body receiver's finish deferred will never be callbacked.
            # So just manually callabck the deferred with the empty string.
            body_receiver.finish.callback("")
        else:
            response.deliverBody(body_receiver)

        body_receiver.finish.addCallback(
            lambda content: ResponseWrapper(response, content))

        return body_receiver.finish

    deferred = agent.request(method, url, headers=headers, bodyProducer=body)
    return deferred.addCallback(deliver_body)
