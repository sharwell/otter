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
from twisted.web.server import Site

from otter.models.mock import MockScalingGroup
from otter.scaling_groups_rest import root, get_store
from otter.util.http import request

from test.utils import fixture


class _PausableSite(Site):
    """
    A site that can be "paused" - a regular ``twisted.web.server.Site`` can't
    really exist between test methods, because ``Site`` schedules updating its
    log date time call, which leaves the reactor unclean because one is always
    scheduled when a test method ends.

    This subclass has pause and resume methods that cancel the scheduled call
    and schedule a new call, respectively.
    """
    def pause(self):
        """
        Cancel the scheduled `_updateLogDateTime()` call
        """
        if (self._logDateTimeCall is not None and
                self._logDateTimeCall.active()):
            self._logDateTimeCall.cancel()
            self._logDateTimeCall = None

    def resume(self):
        """
        Make a call to `_updateLogDateTime()` (which also schedules the next
        such call)
        """
        self._updateLogDateTime()


class WebServiceTestFixture(object):
    """
    A twisted web service test fixture that can run the web service when
    needed, pauses the web service when `cleanupService()` is called, and
    resumes the web service when `buildService()` is called.
    """
    services = {}

    @classmethod
    def buildService(cls, port, resource):
        """
        Creates a web service with the given resource that runs on the given
        port, if no service is running on the port already.  This service can
        be paused by calling `cleanupService()`, but once built, will keep
        running until the reactor shuts down.

        If the web service is already running, resumes it if it is paused.

        Will raise an exception if a different resource's web service is
        already running on the same port.

        :param port: the port to run the web service on
        :type port: ``int``

        :param resource: the resource to use as the root of the site
        :type resource: ``twisted.web.resource.Resource``
        """
        if port not in cls.services:
            cls.services[port] = {
                'resource': resource,
                'site': _PausableSite(resource)
            }
            service = cls.services[port]  # shorthand

            from twisted.internet import reactor
            endpt = endpoints.serverFromString(reactor, 'tcp:{0}'.format(port))

            def on_ready(listening_port):
                service['listening'] = listening_port
                reactor.addSystemEventTrigger("before", "shutdown",
                                              listening_port.stopListening)

            # endpoint.listen() returns a deferred that callbacks with a
            # listening port
            return endpt.listen(service['site']).addCallback(on_ready)

        service = cls.services[port]

        if service['resource'] is not resource:
            raise Exception(
                '{curr!r} is already running on {port} - cannot run {want!r}'
                .format(curr=service['resource'], port=port, want=resource))

        if 'listening' in service:
            service['site'].resume()
            # port.resumeProducing puts the listening port back in the reactor
            return defer.maybeDeferred(service['listening'].resumeProducing)

    @classmethod
    def cleanupService(cls, port):
        """
        Pauses an already existing web service on the given port.

        :param port: the port to run the web service on
        :type port: ``int``
        """
        if port in cls.services:
            service = cls.services[port]
            service['site'].pause()
            if 'listening' in service:
                # port.pauseProducing removes the listening port from the
                # reactor
                return defer.maybeDeferred(service['listening'].pauseProducing)


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
    port = 8080

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

    @defer.inlineCallbacks
    def test_empty_get_all_scaling_groups(self):
        """
        Get list of scaling groups of a tenant ID that has no scaling groups
        """
        wrapper = yield request(self.agent, 'GET',
                                self.get_url('/v1.0/11111/scaling_groups'))
        self.assertEqual(200, wrapper.response.code)
        self.assertEqual(json.loads(wrapper.content), {})

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
        try:
            wrapper = yield request(self.agent, 'GET', headers[0])
        except:
            self.fail("Unable to connect to the URI in the location header")
        else:
            self.assertEqual(wrapper.response.code, 200)
            self.assertEqual(json.load(wrapper.content), config)

    test_create_scaling_group.skip = "Location header currently broken"


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
        return WebServiceTestFixture.buildService(self.port, root)

    def tearDown(self):
        """
        Remove the rest server's listening port from the reactor
        """
        return WebServiceTestFixture.cleanupService(self.port)
