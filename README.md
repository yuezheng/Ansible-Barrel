# Ansible-Barrel
A wrapper of Ansible Python API, provide easier to use invocation methods

Example of task(adhoc):

'''
from ansible_util import TaskRunner

username = "root"
# Get os distribution of target host
task = dict(action=dict(module="setup", args="filter=ansible_distribution*"))

runner = TaskRunner(hosts, default_username, [task],
                    password, key_file)
runner.run()
'''

Get results:

'''
from ansible.plugins.callback import CallbackBase

# Define own result callback class
class TaskCallback(CallbackBase):

    def __init__(self, *args, **kwargs):
        super(TaskCallback, self).__init__(*args, **kwargs)
        self.RESULT = {}
        self.AUTH_FAILED_HOSTS = {}
        self.EXECUTION_FAILED_HOSTS = {}
        self.CONNECTION_FAILED_HOSTS = {}

    def v2_runner_on_ok(self, result, **kwargs):
        host = result._host
        self.RESULT[str(host)] = result._result

    def v2_runner_on_unreachable(self, result):
        host = result._host
        self.CONNECTION_FAILED_HOSTS[str(host)] = result._result
        if 'msg' in result._result:
            if result._result['msg'] == "Authentication failure.":
                self.AUTH_FAILED_HOSTS[str(host)] = result._result

    def v2_runner_on_failed(self, result, ignore_errors=False):
        host = result._host
        self.EXECUTION_FAILED_HOSTS[str(host)] = result._result
        print(result._result)


username = "root"
# Get os distribution of target host
task = dict(action=dict(module="setup", args="filter=ansible_distribution*"))

# Add custom callback for task runner:
runner = TaskRunner(hosts, default_username, [task],
                    password, key_file, callback=TaskCallback())
runner.run()
'''
