"""
Integration tests for the otter rest API (against various model interface
implementations)
"""

from collections import defaultdict
import json
from urlparse import urlunsplit

from twisted.internet import defer, endpoints
from twisted.trial.unittest import TestCase
from twisted.web.client import Agent, RedirectAgent
from twisted.web.http import HTTPChannel
from twisted.web.server import Site

from otter.models.mock import MockScalingGroup
from otter.scaling_groups_rest import root, get_store
from otter.util.http import request

from test.utils import fixture


class DisconnectionNotifyingChannel(HTTPChannel):
    """
    Channel that informs the factory when the connection has been lost
    """
    def connectionLost(self, *args, **kwargs):
        """
        Connection lost that also tells its factory that it has disconnected.
        """
        HTTPChannel.connectionLost(self, *args, **kwargs)
        print 'connectionLost'
        # factory = getattr(self, 'factory', None)
        # if factory:
        #     disconnected = getattr(factory, 'disconnected', None)
        #     if disconnected:
        #         disconnected.callback(None)


class DisconnectionNotifyingSite(Site):
    """
    Site that has a ``disconnected`` deferred that callbacks when the protocol
    has lost its connection.
    """
    protocol = DisconnectionNotifyingChannel
    disconnected = None

    def buildProtocol(self, *args, **kwargs):
        print 'buildProtocol'
        proto = Site.buildProtocol(self, *args, **kwargs)
        self.disconnected = defer.Deferred()
        proto.factory = self
        return proto

    def stopFactory(self, *args, **kwargs):
        print 'stop factory'
        Site.stopFactory(self, *args, **kwargs)
        self.disconnected.callback(None)

    def pause(self):
        if (self._logDateTimeCall is not None and
                self._logDateTimeCall.active()):
            self._logDateTimeCall.cancel()
            self._logDateTimeCall = None

    def resume(self):
        self._updateLogDateTime()


class RestService(object):
    """
    Test resource/fixture builder that can build a REST web service
    """
    listening_port_deferred = None
    listening_port = None
    site = None
    port = 8080

    @classmethod
    def start(cls):
        if cls.site is None:
            from twisted.internet import reactor
            cls.site = DisconnectionNotifyingSite(root)
            endpt = endpoints.serverFromString(reactor,
                                               'tcp:{0}'.format(cls.port))
            cls.listening_port_deferred = endpt.listen(cls.site)

            cls.disconnected = defer.Deferred()

            def stop_it():
                return defer.gatherResults([
                    defer.maybeDeferred(cls.listening_port.stopListening),
                    cls.disconnected,
                    cls.site.disconnected
                ])

            def on_ready(listening_port):
                cls.listening_port = listening_port
                on_connection_lost = listening_port.connectionLost

                def new_connection_lost(*args, **kwargs):
                    print 'connection really lost'
                    on_connection_lost(*args, **kwargs)
                    cls.disconnected.callback(None)

                listening_port.connectionLost = new_connection_lost
                reactor.addSystemEventTrigger("before", "shutdown", stop_it)

            return cls.listening_port_deferred.addCallback(on_ready)
        elif cls.listening_port is not None:
            cls.site.resume()
            return defer.maybeDeferred(cls.listening_port.resumeProducing)

    @classmethod
    def stop(cls):
        if cls.site is not None and cls.listening_port is not None:
            cls.site.pause()
            return defer.maybeDeferred(cls.listening_port.pauseProducing)


class TestRestAbstractBaseMixin(object):
    """
    Base test case for testing the REST API.

    Different implementations of the model interfaces should be tested using a
    subclass of this base case.

    The store should be cleared between every test case and the test fixture
    reloaded at the start of every test case.

    The plan for the case of a DB is that an object can be created that starts
    up a DB, knows how to clear it, load particular fixtures, etc.  Each test
    case can be passed to a function in this instance that loads a fixture
    before every test method (or not), and cleans up after every test calling
    the test case's `addCleanup` method.  Then, the object will shut down the
    DB process when `trial` finishes its run.

    That way the same DB object can be used for other integration tests as well
    (not just this test case), and so the DB only needs to be started once.

    In the case of in-memory stores, fixtures can be loaded and duplicated.
    """
    fixture = "test_rest_fixture.json"
    scheme = 'http'
    port = RestService.port

    _agent = None

    @property
    def agent(self):
        """
        Create a redirect agent if one does not already exist
        """
        if self._agent is None:
            from twisted.internet import reactor
            self._agent = RedirectAgent(Agent(reactor))
        return self._agent

    def get_url(self, path):
        """
        :param path: not the full URL, but the path part of the URL - should
            begin with '/'
        :type path: ``str``

        :return: a url given the test case's hostname, port, scheme, and a path
        :rtype: ``str``
        """
        return urlunsplit(
            (self.scheme, 'localhost:{0}'.format(self.port), path, None, None))

    # @defer.inlineCallbacks
    # def test_empty_get_all_scaling_groups(self):
    #     """
    #     Get list of scaling groups of a tenant ID that has no scaling groups
    #     """
    #     wrapper = yield request(self.agent, 'GET', self.get_url('/v1.0/11111'))
    #     self.assertEqual(200, wrapper.response.code)
    #     self.assertEqual(json.loads(wrapper.content), {})

    # test_empty_get_all_scaling_groups.skip = "This is broken now"

    @defer.inlineCallbacks
    def test_create_scaling_group(self):
        """
        Creating a scaling group with a valid config returns with a 200 OK and
        a Location header pointing to the new scaling group.
        """
        config = {
            'name': 'created',
            'cooldown': 10,
            'min_entities': 1,
            'max_entities': 8,
            'metadata': {
                'somekey': 'somevalue'
            }
        }

        wrapper = yield request(self.agent, 'POST',
                                self.get_url('/v1.0/11111/scaling_groups/dfw'),
                                body=json.dumps(config))
        self.assertEqual(wrapper.response.code, 201,
                         "Create failed: {0}".format(wrapper.content))
        self.assertEqual(wrapper.content, "")

        headers = wrapper.response.headers.getRawHeaders('Location')
        self.assertTrue(headers is not None)
        self.assertEqual(1, len(headers))

        # now make sure the Location header points to something good!
        # try:
        #     wrapper = yield request(self.agent, 'GET', headers[0])
        # except:
        #     self.fail("Unable to connect to the URI in the location header")
        # else:
        #     self.assertEqual(wrapper.response.code, 200)
        #     self.assertEqual(json.load(wrapper.content), config)


class MockStoreRestTestCase(TestRestAbstractBaseMixin, TestCase):
    """
    Use the mock store as the base case
    """
    def setUp(self):
        """
        Replace the store every time with a clean one loaded from a fixture.
        Also, make sure that the rest server's listening port is in the
        reactor.
        """
        # load the fixture into the store
        data = json.loads(fixture(self.fixture))
        for tenant_id in data:
            if tenant_id == "_comment":
                continue
            tenant_dict = defaultdict(dict)
            for group in data[tenant_id]:
                tenant_dict[group['region']][group['id']] = MockScalingGroup(
                    group['region'], group['id'], config=group['config'])
            data[tenant_id] = tenant_dict

        get_store().data = data

        # make sure the rest service is started
        return RestService.start()

    def test_pass(self):
        pass

    def tearDown(self):
        """
        Remove the rest server's listening port from the reactor
        """
        return RestService.stop()
