"""
Deletes.
"""
from cafe.drivers.unittest.decorators import tags
from test_repo.autoscale.fixtures import AutoscaleFixture


class DeleteAll(AutoscaleFixture):

    """
    Get list of groups/servers on account and delete them
    """

    @tags(type='group')
    def test_delete_all_groups_on_account(self):
        """
        Delete all groups on the account
        """
        list_groups_response = self.autoscale_client.list_scaling_groups()
        list_groups = list_groups_response.entity
        for each_group in list_groups:
            self.empty_scaling_group(each_group)
            self.autoscale_client.delete_scaling_group(each_group.id)
        list_groups_again = (self.autoscale_client.list_scaling_groups()).entity
        print 'Deleting {0} groups, {1} still exist'.format(len(list_groups), len(list_groups_again))\
            if len(list_groups_again) is not 0 else "Deleted {0} groups".format(len(list_groups))

    @tags(type='servers')
    def test_delete_all_servers_on_account(self):
        """
        Deletes all servers on the account
        """
        all_servers = (self.server_client.list_servers()).entity
        server_id_list = []
        for each_server in all_servers:
            server_id_list.append(each_server.id)
        for each_server_id in server_id_list:
            self.server_client.delete_server(each_server_id)
        list_servers = (self.server_client.list_servers()).entity
        print 'Deleting {0} servers, {1} still exist'.format(len(all_servers), len(list_servers))\
            if len(list_servers) is not 0 else "Deleted {0} servers".format(len(all_servers))
