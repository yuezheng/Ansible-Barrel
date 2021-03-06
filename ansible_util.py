#  -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
The wrapper of Ansible Runner for Task and Playbook
Reference from Ansible Python API Example:
     http://docs.ansible.com/ansible/latest/dev_guide/developing_api.html
"""

import shutil
from collections import namedtuple

from ansible import constants as C
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play import Play
from ansible.plugins.callback import CallbackBase
from ansible.plugins.callback.json import CallbackModule
from ansible.vars.manager import VariableManager

PLAY_NAME = "Ansible Play"


class ResultsCollector(CallbackBase):
    """Default callback of task runner"""

    def __init__(self, *args, **kwargs):
        super(ResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        self.host_unreachable[result._host.get_name()] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        self.host_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.host_failed[result._host.get_name()] = result


class PlaybookResultsCollector(CallbackModule):
    """Default callback of playbook runner"""

    def __init__(self, *args, **kwargs):
        super(PlaybookResultsCollector, self).__init__(*args, **kwargs)
        self.RESULT = []

    def v2_playbook_on_stats(self, stats):
        super(PlaybookResultsCollector, self).v2_playbook_on_stats(stats)

        for play in self.results:
            for task in play.get("tasks", []):
                res = task["task"]
                res["hosts"] = {}
                for ip, detail in task["hosts"].items():
                    _failed = False
                    if detail.get("stderr"):
                        _failed = True
                    res["hosts"][ip] = {
                        "stderr": detail.get("stderr"),
                        "stdout": detail.get("stdout"),
                        "success": not _failed
                    }
                    self.RESULT.append(res)


class BaseRunner(object):
    """Base Runner for tasks and playbook."""
    def __init__(self, hosts=None, username=None, password=None, key_file=None,
                 timeout=None, ssh_retries=6):
        if type(hosts) is list:
            self.hosts = hosts
        if type(hosts) is str:
            self.hosts = [hosts]
        self._create_inventory()

        self._set_options(username, module_path='',
                          key_file=key_file,
                          ssh_retries=ssh_retries,
                          timeout=timeout)
        self.password = password
        self.key_file = key_file

    def _create_inventory(self):
        # create inventory and pass to variable manager
        self.loader = DataLoader()

        # create inventory, use path to host config file as source or
        # hosts in a comma separated string
        _hosts = ','.join(self.hosts) + ','
        self.inventory = InventoryManager(
            loader=self.loader,
            sources=_hosts)
        # variable manager takes care of merging all the different sources
        # to give you a unifed view of variables available in each context
        self.variable_manager = VariableManager(loader=self.loader,
                                                inventory=self.inventory)

    def _set_options(self, username=None, forks=100, become=None,
                     become_method=None, become_user=None, check=False,
                     key_file=None,
                     module_path="/to/mymodules",
                     ssh_retries=6,
                     timeout=None):
        # since API is constructed for CLI it expects certain options to
        # always be set, named tuple 'fakes' the args parsing options object
        Options = namedtuple('Options',
                            ['connection',
                             'remote_user',
                             'module_path',
                             'forks',
                             'become',
                             'become_method',
                             'become_user',
                             'check',
                             'private_key_file',
                             'diff',
                             'listhosts',
                             'listtasks',
                             'listtags',
                             'syntax'])
        self.options = Options(connection='ssh',
                               remote_user=username,
                               module_path=[module_path],
                               forks=forks,
                               become=become,
                               become_method=become_method,
                               become_user=become_user,
                               check=check,
                               private_key_file=key_file,
                               diff=False,
                               listhosts=None,
                               listtasks=None,
                               listtags=None,
                               syntax=None)
        C.HOST_KEY_CHECKING = False
        C.DEPRECATION_WARNINGS = False
        C.ANSIBLE_SSH_RETRIES = ssh_retries
        C.COMMAND_WARNINGS = False

    def set_extra_vars(self, extra_vars):
        self.variable_manager.__setstate__({"extra_vars": extra_vars})


class TaskRunner(BaseRunner):
    """Task Runner for initialize Ansible API."""

    def __init__(self, hosts, username, tasks,
                 password=None, key_file=None,
                 timeout=None, ssh_retries=6,
                 result_callback=None):
        """Construct task ansbile task runner and prepare arguments

        :param hosts: List of host ip address
        :param username: Username used to ssh login
        :param password: Password used to ssh login
        :param key_file: ssh key used to ssh login
        :param tasks: List of task definition
        :param result_callback: Instance of class inherited from BaseCallback
        :param ssh_retries: Retries for ssh connection failed
        """
        super(TaskRunner, self).__init__(hosts, username, password, key_file, timeout, ssh_retries)

        self.tasks = tasks
        self._create_source()

        if result_callback:
            self.callback = result_callback
        else:
            self.callback = ResultsCollector()

        self._create_tqm()

    def _create_tqm(self):
        if self.password:
            passwords = {"conn_pass": self.password}
        elif self.key_file:
            passwords = None
        else:
            passwords = {"vault_pass": "secret"}
        self.tqm = TaskQueueManager(
            inventory=self.inventory,
            variable_manager=self.variable_manager,
            loader=self.loader,
            options=self.options,
            passwords=passwords,
            stdout_callback=self.callback
        )

    def _create_source(self):
        self.play_source = dict(
            name=PLAY_NAME,
            hosts=self.hosts,
            gather_facts='no',
            tasks=self.tasks
        )
        self.play = Play().load(self.play_source,
                                variable_manager=self.variable_manager,
                                loader=self.loader)

    def run(self):
        try:
            self.tqm.run(self.play)
        finally:
            if self.tqm is not None:
                self.tqm.cleanup()
            # Remove ansible tmpdir
            shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)


class PlaybookRunner(BaseRunner):

    def __init__(self, hosts, username, playbook,
                 password=None, key_file=None,
                 timeout=None, ssh_retries=6,
                 result_callback=None):
        super(PlaybookRunner, self).__init__(hosts, username, password, key_file,
                                             timeout, ssh_retries)
        self.playbook = playbook
        if result_callback:
            self.callback = result_callback
        else:
            self.callback = PlaybookResultsCollector()

        self.options
        self._create_executor()

    def _create_executor(self):
        if self.password:
            passwords = {"conn_pass": self.password}
        elif self.key_file:
            passwords = None
        else:
            passwords = {"vault_pass": "secret"}
        self.executor = PlaybookExecutor([self.playbook], self.inventory,
                                         self.variable_manager, self.loader,
                                         self.options, passwords)
        self.executor._tqm._stdout_callback = self.callback

    def run(self):
        try:
            self.executor.run()
        finally:
            shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)
