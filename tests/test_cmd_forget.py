import contextlib
import unittest
from io import StringIO

from doit.exceptions import InvalidCommand
from doit.dependency import DbmDB, Dependency
from doit.cmd_base import ModuleTaskLoader
from doit.cmd_forget import Forget
from doit.doit_cmd import DoitMain
from tests.support import tasks_sample, CmdFactory, DepfileNameMixin


class TestCmdForget(DepfileNameMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.tasks = tasks_sample()

    @staticmethod
    def _add_task_deps(tasks, testdb):
        """put some data on testdb"""
        dep = Dependency(DbmDB, testdb)
        for task in tasks:
            dep._set(task.name, "dep", "1")
        dep.close()

        dep2 = Dependency(DbmDB, testdb)
        assert "1" == dep2._get("g1.a", "dep")
        dep2.close()

    def testForgetDefault(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(Forget, outstream=output, dep_file=self.depfile_name,
                                backend='dbm', task_list=self.tasks,
                                sel_tasks=['t1', 't2'])
        cmd_forget._execute(False, False, False)
        got = output.getvalue().split("\n")[:-1]
        self.assertEqual(["forgetting t1", "forgetting t2"], got)
        dep = Dependency(DbmDB, self.depfile_name)
        self.assertIsNone(dep._get('t1', "dep"))
        self.assertIsNone(dep._get('t2', "dep"))
        self.assertEqual('1', dep._get('t3', "dep"))

    def testForgetAll(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(Forget, outstream=output, dep_file=self.depfile_name,
                                backend='dbm', task_list=self.tasks, sel_tasks=[])
        cmd_forget._execute(False, False, True)
        got = output.getvalue().split("\n")[:-1]
        self.assertEqual(["forgetting all tasks"], got)
        dep = Dependency(DbmDB, self.depfile_name)
        for task in self.tasks:
            self.assertIsNone(dep._get(task.name, "dep"))

    def testDisableDefault(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(Forget, outstream=output, dep_file=self.depfile_name,
                                backend='dbm', task_list=self.tasks,
                                sel_tasks=['t1', 't2'], sel_default_tasks=True)
        cmd_forget._execute(False, True, False)
        got = output.getvalue().split("\n")[:-1]
        self.assertEqual(
            ["no tasks specified, pass task name, --enable-default or --all"], got)
        dep = Dependency(DbmDB, self.depfile_name)
        for task in self.tasks:
            self.assertEqual("1", dep._get(task.name, "dep"))

    def testForgetOne(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(Forget, outstream=output, dep_file=self.depfile_name,
                                backend='dbm', task_list=self.tasks,
                                sel_tasks=["t2", "t1"])
        cmd_forget._execute(False, True, False)
        got = output.getvalue().split("\n")[:-1]
        self.assertEqual(["forgetting t2", "forgetting t1"], got)
        dep = Dependency(DbmDB, self.depfile_name)
        self.assertIsNone(dep._get("t1", "dep"))
        self.assertIsNone(dep._get("t2", "dep"))
        self.assertEqual("1", dep._get("g1.a", "dep"))

    def testForgetGroup(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(
            Forget, outstream=output, dep_file=self.depfile_name,
            backend='dbm', task_list=self.tasks, sel_tasks=["g1"])
        cmd_forget._execute(False, False, False)
        got = output.getvalue().split("\n")[:-1]
        self.assertEqual("forgetting g1", got[0])

        dep = Dependency(DbmDB, self.depfile_name)
        self.assertEqual("1", dep._get("t1", "dep"))
        self.assertEqual("1", dep._get("t2", "dep"))
        self.assertIsNone(dep._get("g1", "dep"))
        self.assertIsNone(dep._get("g1.a", "dep"))
        self.assertIsNone(dep._get("g1.b", "dep"))

    def testForgetTaskDependency(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(
            Forget, outstream=output, dep_file=self.depfile_name,
            backend='dbm', task_list=self.tasks, sel_tasks=["t3"])
        cmd_forget._execute(True, False, False)
        dep = Dependency(DbmDB, self.depfile_name)
        self.assertIsNone(dep._get("t3", "dep"))
        self.assertIsNone(dep._get("t1", "dep"))

    # if task dependency not from a group dont forget it
    def testDontForgetTaskDependency(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(
            Forget, outstream=output, dep_file=self.depfile_name,
            backend='dbm', task_list=self.tasks, sel_tasks=["t3"])
        cmd_forget._execute(False, False, False)
        dep = Dependency(DbmDB, self.depfile_name)
        self.assertIsNone(dep._get("t3", "dep"))
        self.assertEqual("1", dep._get("t1", "dep"))

    def testForgetNoSelectionNoDefault(self):
        # no task names from command line and no 'default_tasks'
        # configured (sel_tasks is None): forget all tasks instead
        # of crashing with a TypeError (issue #478)
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(Forget, outstream=output, dep_file=self.depfile_name,
                                backend='dbm', task_list=self.tasks,
                                sel_tasks=None, sel_default_tasks=True)
        cmd_forget._execute(False, False, False)
        got = output.getvalue().split("\n")[:-1]
        # every task forgotten exactly once, including group subtasks
        self.assertEqual(["forgetting %s" % task.name for task in self.tasks], got)
        dep = Dependency(DbmDB, self.depfile_name)
        for task in self.tasks:
            self.assertIsNone(dep._get(task.name, "dep"))

    def testForgetNoSelectionFollowSub(self):
        # same as above but following task dependencies: shared
        # dependencies must still be forgotten only once
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(Forget, outstream=output, dep_file=self.depfile_name,
                                backend='dbm', task_list=self.tasks,
                                sel_tasks=None, sel_default_tasks=True)
        cmd_forget._execute(True, False, False)
        got = output.getvalue().split("\n")[:-1]
        self.assertEqual(len(got), len(set(got)))
        dep = Dependency(DbmDB, self.depfile_name)
        for task in self.tasks:
            self.assertIsNone(dep._get(task.name, "dep"))

    def testForgetInvalid(self):
        self._add_task_deps(self.tasks, self.depfile_name)
        output = StringIO()
        cmd_forget = CmdFactory(
            Forget, outstream=output, dep_file=self.depfile_name,
            backend='dbm', task_list=self.tasks, sel_tasks=["XXX"])
        self.assertRaises(InvalidCommand, cmd_forget._execute, False, False, False)


def _forget_dodo():
    """sample dodo namespace with two independent tasks"""
    def task_one():
        return {'actions': []}

    def task_two():
        return {'actions': []}

    return {'task_one': task_one, 'task_two': task_two}


class TestForgetMain(DepfileNameMixin, unittest.TestCase):
    """end-to-end tests through DoitMain (issues #469 and #478)"""

    def _seed_db(self):
        dep = Dependency(DbmDB, self.depfile_name)
        dep._set('one', "dep", "1")
        dep._set('two', "dep", "1")
        dep.close()

    def _run_forget(self, extra_global):
        global_config = {'dep_file': self.depfile_name}
        global_config.update(extra_global)
        main = DoitMain(ModuleTaskLoader(_forget_dodo()),
                        config_filenames=(),
                        extra_config={'GLOBAL': global_config})
        out = StringIO()
        with contextlib.redirect_stdout(out):
            main.run(['forget'])
        return out.getvalue()

    def testForgetDefaultTasksFromExtraConfig(self):
        # 'default_tasks' passed through DoitMain(extra_config=...)
        # must be honored by `forget`, not only DOIT_CONFIG (issue #469)
        self._seed_db()
        output = self._run_forget({'default_tasks': ['one']})
        self.assertIn("forgetting one", output)
        self.assertNotIn("forgetting two", output)
        dep = Dependency(DbmDB, self.depfile_name)
        self.assertIsNone(dep._get('one', "dep"))
        self.assertEqual('1', dep._get('two', "dep"))

    def testForgetNoDefaultTasksAtAll(self):
        # no 'default_tasks' anywhere: `forget` forgets all tasks
        # instead of raising TypeError (issue #478)
        self._seed_db()
        output = self._run_forget({})
        self.assertIn("forgetting one", output)
        self.assertIn("forgetting two", output)
        dep = Dependency(DbmDB, self.depfile_name)
        self.assertIsNone(dep._get('one', "dep"))
        self.assertIsNone(dep._get('two', "dep"))
