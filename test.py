from ansible.plugins.callback import CallbackBase

from ansible_util import TaskRunner
from ansible_util import PlaybookRunner
from ansible_util import PlaybookResultsCollector

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

hosts = ["192.168.6.106"]
account = "root"

def test_task():
    task = dict(action=dict(module="setup", args="filter=ansible_distribution*"))
    result_collector = TaskCallback()

    runner = TaskRunner(hosts, account, [task], result_callback=result_collector)
    runner.run()
    print(result_collector.RESULT)

 
def test_playbook():
    callback = PlaybookResultsCollector()

    playbook_path = "./test_playbook.yml"
    runner = PlaybookRunner(hosts, account, playbook_path, result_callback=callback)
    runner.run()

    print(callback.results)


if __name__ == "__main__":
    test_playbook()
