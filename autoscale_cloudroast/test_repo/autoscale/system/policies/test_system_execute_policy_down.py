"""
System tests for execute scale down policies
"""
from test_repo.autoscale.fixtures import AutoscaleFixture


class ExecutePoliciesDownTest(AutoscaleFixture):

    """
    System tests to verify execute scale down policies
    """

    @classmethod
    def setUpClass(cls):
        """
        Instantiate client, behaviors and configs
        """
        super(ExecutePoliciesDownTest, cls).setUpClass()

    def setUp(self):
        """
        Create a scaling group with minentities as 2 and scale up by 2
        """
        minentities = 2
        self.create_group_response = self.autoscale_behaviors.create_scaling_group_given(
            gc_min_entities=minentities,
            gc_cooldown=0)
        self.group = self.create_group_response.entity
        self.policy_up = {'change': 2}
        self.autoscale_behaviors.create_policy_webhook(
            group_id=self.group.id,
            policy_data=self.policy_up,
            execute_policy=True)
        self.resources.add(self.group.id,
                           self.autoscale_client.delete_scaling_group)

    def tearDown(self):
        """
        Emptying the scaling group by updating minentities=maxentities=0,
        which is then deleted by the Autoscale fixture's teardown
        """
        self.empty_scaling_group(self.group)

    def test_system_scale_down_policy_execution_change(self):
        """
        Verify the execution of a scale down policy with change
        """
        policy_down = {'change': - self.policy_up['change']}
        execute_scale_down_policy = self.autoscale_behaviors.create_policy_webhook(
            group_id=self.group.id,
            policy_data=policy_down,
            execute_policy=True)
        self.assertEquals(execute_scale_down_policy[
                          'execute_response'], 202,
                          msg='Scale down policy execution with change for group {} failed with {}'
                          .format(self.group.id, execute_scale_down_policy['execute_response']))
        self.autoscale_behaviors.wait_for_expected_number_of_active_servers(
            group_id=self.group.id,
            expected_servers=self.group.groupConfiguration.minEntities)

    def test_system_scale_down_policy_execution_change_percent(self):
        """
        Verify the execution of a scale down policy with change percent
        """
        policy_down = {'change_percent': -60}
        execute_change_percent_policy = self.autoscale_behaviors.create_policy_webhook(
            group_id=self.group.id,
            policy_data=policy_down,
            execute_policy=True)
        self.assertEquals(execute_change_percent_policy[
                          'execute_response'], 202)
        servers_from_scale_down = self.autoscale_behaviors.calculate_servers(
            current=self.group.groupConfiguration.minEntities +
            self.policy_up['change'],
            percentage=policy_down['change_percent'])
        self.autoscale_behaviors.wait_for_expected_number_of_active_servers(
            group_id=self.group.id,
            expected_servers=servers_from_scale_down)

    def test_system_scale_down_policy_execution_desired_capacity(self):
        """
        Verify the execution of a scale down policy with desired capacity
        """
        policy_down = {
            'desired_capacity': self.group.groupConfiguration.minEntities}
        execute_desired_capacity_policy = self.autoscale_behaviors.create_policy_webhook(
            group_id=self.group.id,
            policy_data=policy_down,
            execute_policy=True)
        self.assertEquals(execute_desired_capacity_policy[
                          'execute_response'], 202)
        self.autoscale_behaviors.wait_for_expected_number_of_active_servers(
            group_id=self.group.id,
            expected_servers=policy_down['desired_capacity'])

    def test_system_execute_scale_down_below_minentities_change(self):
        """
        Verify execution of scale down policy when change results in servers less than
        minentities of the scaling group, is successful when desired capacity > minentities
        """
        policy_down = {'change': - 100}
        execute_change_policy = self.autoscale_behaviors.create_policy_webhook(
            group_id=self.group.id,
            policy_data=policy_down,
            execute_policy=True)
        self.assertEquals(execute_change_policy['execute_response'], 202,
                          msg='Scale down policy execution failed when minentities limit is met: {}'
                          'for group {}'
                          .format(execute_change_policy['execute_response'], self.group.id))
        self.autoscale_behaviors.wait_for_expected_number_of_active_servers(
            group_id=self.group.id,
            expected_servers=self.group.groupConfiguration.minEntities)

    def test_system_execute_scale_down_below_minentities_change_percent(self):
        """
        Verify execution of scale down policy when change percent results in servers less than
        minentities of the scaling group
        """
        policy_down = {'change_percent': - 300}
        execute_change_policy = self.autoscale_behaviors.create_policy_webhook(
            group_id=self.group.id,
            policy_data=policy_down,
            execute_policy=True)
        self.assertEquals(execute_change_policy['execute_response'], 202,
                          msg='Scale down policy execution failed when minentities limit is met: {}'
                          ' for group {}'
                          .format(execute_change_policy['execute_response'], self.group.id))
        self.autoscale_behaviors.wait_for_expected_number_of_active_servers(
            group_id=self.group.id,
            expected_servers=self.group.groupConfiguration.minEntities)

    def test_system_execute_scale_down_below_minentities_desired_capacity(self):
        """
        Verify execution of scale down policy when desired capacity less than minentities
        of the scaling group
        """
        policy_down = {
            'desired_capacity': self.group.groupConfiguration.minEntities - 1}
        execute_change_policy = self.autoscale_behaviors.create_policy_webhook(
            group_id=self.group.id,
            policy_data=policy_down,
            execute_policy=True)
        self.assertEquals(execute_change_policy['execute_response'], 202,
                          msg='Scale down policy execution failed when minentities limit is met: {}'
                          ' for group {}'
                          .format(execute_change_policy['execute_response'], self.group.id))
        self.autoscale_behaviors.wait_for_expected_number_of_active_servers(
            group_id=self.group.id,
            expected_servers=self.group.groupConfiguration.minEntities)
