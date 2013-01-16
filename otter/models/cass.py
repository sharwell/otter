"""
 Mock interface for the front-end scaling groups engine
"""
from otter.models.interface import (IScalingGroup, IScalingGroupCollection,
                                    NoSuchScalingGroupError)
import zope.interface

from twisted.internet import defer
from otter.util.cqlbatch import Batch
from otter.util.hashkey import generate_random_str

import json


class CassBadDataError(Exception):
    """
    Error to be raised when attempting operations on an entity that does not
    exist.
    """
    pass


def _serial_json_data(data, ver):
    dataOut = data.copy()
    dataOut["_ver"] = ver
    return json.dumps(dataOut)


class CassScalingGroup:
    """
    Mock scaling group record

    :ivar tenant_id: the tenant ID of the scaling group - once set, should not
        be updated
    :type tenant_id: ``str``

    :ivar uuid: UUID of the scaling group - once set, cannot be updated
    :type uuid: ``str``

    :ivar config: group configuration values, as specified by
        :data:`otter.json_schema.scaling_group.config`
    :type config: ``dict``

    :ivar launch: launch configuration, as specified by
        :data:`otter.json_schema.scaling_group.config`
    :type config: ``dict``

    :ivar policies: scaling policies of the group, each of which is specified
        by :data:`otter.json_schema.scaling_group.scaling_policy`
    :type config: ``list``

    :ivar steady: the desired steady state number of entities -
        defaults to the minimum if not given.  This how many entities the
        system thinks there should be.  It is like a variable used by
        the scaling system to keep track of how many servers there should be,
        as opposed to constants like the minimum and maximum (which constrain
        what values the ``steady_state`` can be).
    :type steady_state: ``int``

    :ivar active_entities: the entity id's corresponding to the active
        entities in this scaling group
    :type active_entities: ``list``

    :ivar pending_entities: the entity id's corresponding to the pending
        entities in this scaling group
    :type pending_entities: ``list``

    :ivar running: whether the scaling is currently running, or paused
    :type entities: ``bool``
    """
    zope.interface.implements(IScalingGroup)

    def __init__(self, tenant_id, uuid, connection, cflist):
        """
        Creates a MockScalingGroup object.  If the actual scaling group should
        be created, a creation argument is provided containing the config, the
        launch config, and optional scaling policies.
        """
        self.tenant_id = tenant_id
        self.uuid = uuid
        self.connection = connection
        self.cflist = cflist

    def view_manifest(self):
        pass

    def view_config(self):
        """
        :return: :class:`Deferred` that fires with a view of the config
        """
        query = "SELECT data FROM "
        query += self.cflist["config"]
        varcl = " WHERE accountId = :accountId AND groupId = :groupId"
        d = self.connection.execute(query + varcl + ";",
                                    {"accountId": self.tenant_id,
                                        "groupId": self.uuid})
        d.addCallback(self._grab_json_data)
        return d

    def view_launch_config(self):
        """
        :return: :class:`Deferred` that fires with a view of the launch config
        """
        query = "SELECT data FROM "
        query += self.cflist["launch"]
        varcl = " WHERE accountId = :accountId AND groupId = :groupId"
        d = self.connection.execute(query + varcl + ";",
                                    {"accountId": self.tenant_id,
                                        "groupId": self.uuid})
        d.addCallback(self._grab_json_data)
        return d

    def view_state(self):
        """
        :return: :class:`Deferred` that fires with a view of the state
        """
        pass

    def update_config(self, data):
        """
        Update the scaling group configuration paramaters based on the
        attributes in ``data``.

        :return: :class:`Deferred` that fires with None
        """
        def _do_update_config(lastRev):
            # IMPORTANT REMINDER: lastRev contains the previous
            # state.... but you can't be guaranteed that the
            # previous state hasn't changed between when you
            # got it back from Cassandra and when you are
            # sending your new insert request.
            cqlstr = "INSERT INTO " + self.cflist["config"]
            cqlstr += "(accountId, groupId, data) VALUES (:accountId, :groupId, :scaling)"
            queries = [cqlstr
                       ]
            b = Batch(queries, {"accountId": self.tenant_id,
                                "groupId": self.uuid,
                                "scaling": _serial_json_data(data, 1)})
            d = b.execute(self.connection)
            return d

        d = self._ensure_there()
        d.addCallback(_do_update_config)
        return d

    def update_launch_config(self, data):
        """
        Update the launch config parameters based on the attributes in
        ``data``.  Overwrites the existing launch config.  Note - no error
        checking here happens, so it's possible to get the launch config into
        an improper state.
        """
        def _do_update_launch(lastRev):
            # IMPORTANT REMINDER: lastRev contains the previous
            # state.... but you can't be guaranteed that the
            # previous state hasn't changed between when you
            # got it back from Cassandra and when you are
            # sending your new insert request.
            cqlstr = "INSERT INTO " + self.cflist["launch"]
            cqlstr += "(accountId, groupId, data) VALUES (:accountId, :groupId, :launch)"
            queries = [
                cqlstr]
            b = Batch(queries, {"accountId": self.tenant_id,
                                "groupId": self.uuid,
                                "launch": _serial_json_data(data, 1)})
            d = b.execute(self.connection)
            return d

        d = self._ensure_there()
        d.addCallback(_do_update_launch)
        return d

    def set_steady_state(self, steady_state):
        """
        Sets the steady state value

        :param steady_state: value to set the steady state to, but will not set
            to anything below the minimum or above the maximum
        :type steady_state: ``int``

        :return: :class:`Deferred` that fires with None
        """
        pass

    def bounce_entity(self, entity_id):
        """
        Rebuilds a entity given by the server ID

        :return: :class:`Deferred` that fires with None
        """
        pass

    def list_policies(self):
        """
        :return: a dict of the policies, as specified by
            :data:`otter.json_schema.scaling_group.policy_list`
        :rtype: a :class:`twisted.internet.defer.Deferred` that fires with
            ``dict``
        """
        pass

    def get_policy(self, policy_id):
        """
        :return: a policy, as specified by
            :data:`otter.json_schema.scaling_group.policy`
        :rtype: a :class:`twisted.internet.defer.Deferred` that fires with
            ``dict``
        """
        pass

    def create_policy(self, data):
        """
        Creates a new policy with the data given.

        :param data: the details of the scaling policy in JSON format
        :type data: ``list`` of ``dict``

        :return: the UUID of the newly created scaling policy
        """
        pass

    def update_policy(self, policy_id, data):
        """
        Updates an existing policy with the data given.

        :param policy_id: the uuid of the entity to update
        :type policy_id: ``str``

        :param data: the details of the scaling policy in JSON format
        :type data: ``dict``

        :return: a policy, as specified by
            :data:`otter.json_schema.scaling_group.policy`
        :rtype: a :class:`twisted.internet.defer.Deferred` that fires with
            ``dict``
        """
        pass

    def delete_policy(self, policy_id):
        """
        Delete the scaling policy

        :param policy_id: the ID of the policy to be deleted
        :type policy_id: ``str``

        :return: a :class:`twisted.internet.defer.Deferred` that fires with None

        :raises: :class:`NoSuchPolicyError` if the policy id does not exist
        """
        pass

    def _ensure_there(self):
        query = "SELECT data FROM " + self.cflist["config"]
        varcl = " WHERE accountId = :accountId AND groupId = :groupId"
        d = self.connection.execute(query + varcl + ";",
                                    {"accountId": self.tenant_id,
                                        "groupId": self.uuid})
        d.addCallback(self._grab_json_data)
        return d

    def _grab_json_data(self, rawResponse):
        if rawResponse is None:
            err = CassBadDataError("None")
            return defer.fail(err)
        if len(rawResponse) == 0:
            err = NoSuchScalingGroupError(self.tenant_id, self.uuid)
            return defer.fail(err)
        if 'cols' not in rawResponse[0]:
            err = CassBadDataError("No cols")
            return defer.fail(err)
        rec = None
        for rawRec in rawResponse[0]['cols']:
            if rawRec['name'] is 'data':
                rec = rawRec['value']
        if rec is None:
            err = CassBadDataError("No data")
            return defer.fail(err)
        data = None
        try:
            data = json.loads(rec)
            if "_ver" in data:
                del data["_ver"]
            return defer.succeed(data)
        except ValueError:
            err = CassBadDataError("Bad data")
            return defer.fail(err)


class CassScalingGroupCollection:
    """
    Scaling group collections

    The structure..

    Configs:
    CF = scaling_config
    RK = accountID
    CK = groupID

    Launch Configs (mirrors config):
    CF = launch_config
    RK = accountID
    CK = groupID

    Scaling Policies (doesn't mirror config):
    CF = policies
    RK = accountID
    CK = groupID:polID
    """
    zope.interface.implements(IScalingGroupCollection)

    def __init__(self, connection, cflist):
        """
        Init

        :param connection: Thrift connection to use

        :param cflist: Column family list
        """
        self.connection = connection
        self.cflist = cflist

    def create_scaling_group(self, tenant_id, config, launch, policies=None):
        """
        Create scaling group based on the tenant id, the configuration
        paramaters, the launch config, and optional scaling policies.

        :param tenant_id: the tenant ID of the tenant the scaling group
            belongs to
        :type tenant_id: ``str``

        :param config: scaling group configuration options in JSON format, as
            specified by :data:`otter.json_schema.scaling_group.config`
        :type data: ``dict``

        :param launch: scaling group launch configuration options in JSON
            format, as specified by
            :data:`otter.json_schema.scaling_group.launch_config`
        :type data: ``dict``

        :param policies: list of scaling group policies, each one given as a
            JSON blob as specified by
            :data:`otter.json_schema.scaling_group.scaling_policy`
        :type data: ``list`` of ``dict``

        :return: uuid of the newly created scaling group
        :rtype: a :class:`twisted.internet.defer.Deferred` that fires with `str`
        """

        scaling_group_id = generate_random_str(10)

        insertinto = "INSERT INTO "
        cols = "(accountId, groupId, data) VALUES (:accountId, :groupId, "

        queries = [
            insertinto + self.cflist["config"] + cols + ":scaling)",
            insertinto + self.cflist["launch"] + cols + ":launch)"]
        b = Batch(queries, {"accountId": tenant_id,
                            "groupId": scaling_group_id,
                            "scaling": _serial_json_data(config, 1),
                            "launch": _serial_json_data(launch, 1),
                            })
        d = b.execute(self.connection)
        return d

    def delete_scaling_group(self, tenant_id, scaling_group_id):
        """
        Delete the scaling group

        :param tenant_id: the tenant ID of the scaling groups
        :type tenant_id: ``str``

        :param scaling_group_id: the uuid of the scaling group to delete
        :type scaling_group_id: ``str``

        :return: a :class:`twisted.internet.defer.Deferred` that fires with None

        :raises: :class:`NoSuchScalingGroupError` if the scaling group id
            doesn't exist for this tenant id
        """

        varcl = " WHERE accountId = :accountId AND groupId = :groupId"

        queries = [
            "DELETE FROM " + self.cflist["config"] + varcl,
            "DELETE FROM " + self.cflist["launch"] + varcl,
            "DELETE FROM scaling_policies" + varcl]
        b = Batch(
            queries, {"accountId": tenant_id, "groupId": scaling_group_id})
        b.execute(self.connection)

    def list_scaling_groups(self, tenant_id):
        """
        List the scaling groups for this tenant ID

        :param tenant_id: the tenant ID of the scaling groups
        :type tenant_id: ``str``

        :return: a list of scaling groups
        :rtype: a :class:`twisted.internet.defer.Deferred` that fires with a
            ``list`` of :class:`IScalingGroup` providers
        """

        def _grab_list(rawResponse):
            if rawResponse is None:
                err = CassBadDataError("None")
                return defer.fail(err)
            if len(rawResponse) == 0:
                err = NoSuchScalingGroupError(self.tenant_id, self.uuid)
                return defer.fail(err)
            data = []
            for row in rawResponse:
                if 'cols' not in row:
                    err = CassBadDataError("No cols")
                    return defer.fail(err)
                rec = None
                for rawRec in row['cols']:
                    if rawRec['name'] is 'groupid':
                        rec = rawRec['value']
                if rec is None:
                    err = CassBadDataError("No data")
                    return defer.fail(err)
                data.append(CassScalingGroup(tenant_id, rec,
                                             self.connection, self.cflist))
            return defer.succeed(data)

        query = "SELECT groupid FROM " + self.cflist["config"]
        varcl = " WHERE accountId = :accountId;"
        d = self.connection.execute(query + varcl + ";",
                                    {"accountId": tenant_id})
        d.addCallback(_grab_list)
        return d

    def get_scaling_group(self, tenant_id, scaling_group_id):
        """
        Get a scaling group model

        Will return a scaling group even if the ID doesn't exist,
        but the scaling group will throw exceptions when you try to do things
        with it.

        :param tenant_id: the tenant ID of the scaling groups
        :type tenant_id: ``str``

        :return: scaling group model object
        :rtype: :class:`IScalingGroup` provider (no
            :class:`twisted.internet.defer.Deferred`)
        """
        return CassScalingGroup(tenant_id, scaling_group_id,
                                self.connection, self.cflist)
