from __future__ import print_function
import os
import platform
import subprocess
import sys
import tempfile
import textwrap

from timing import monotonic_time_nanos
from tracing import Tracing
from buck_tool import BuckTool, which, check_output
from buck_tool import BuckToolException, RestartBuck


JAVA_CLASSPATHS = [
    "src",
    "build/abi_processor/classes",
    "build/classes",
    "build/dx_classes",
    "third-party/java/aopalliance/aopalliance.jar",
    "third-party/java/args4j/args4j-2.0.30.jar",
    "third-party/java/ddmlib/ddmlib-22.5.3.jar",
    "third-party/java/guava/guava-18.0.jar",
    "third-party/java/guice/guice-3.0.jar",
    "third-party/java/guice/guice-assistedinject-3.0.jar",
    "third-party/java/guice/guice-multibindings-3.0.jar",
    "third-party/java/ini4j/ini4j-0.5.2.jar",
    "third-party/java/jackson/jackson-annotations-2.0.5.jar",
    "third-party/java/jackson/jackson-core-2.0.5.jar",
    "third-party/java/jackson/jackson-databind-2.0.5.jar",
    "third-party/java/jackson/jackson-datatype-jdk7-2.5.0.jar",
    "third-party/java/jsr/javax.inject-1.jar",
    "third-party/java/jsr/jsr305.jar",
    "third-party/java/icu4j/icu4j-54.1.1.jar",
    "third-party/java/nailgun/nailgun-server-0.9.2-SNAPSHOT.jar",
    "third-party/java/android/sdklib.jar",
    "third-party/java/asm/asm-debug-all-5.0.3.jar",
    "third-party/java/astyanax/astyanax-cassandra-1.56.38.jar",
    "third-party/java/astyanax/astyanax-core-1.56.38.jar",
    "third-party/java/astyanax/astyanax-thrift-1.56.38.jar",
    "third-party/java/astyanax/cassandra-1.2.3.jar",
    "third-party/java/astyanax/cassandra-thrift-1.2.3.jar",
    "third-party/java/astyanax/commons-cli-1.1.jar",
    "third-party/java/astyanax/commons-codec-1.2.jar",
    "third-party/java/astyanax/commons-lang-2.6.jar",
    "third-party/java/astyanax/high-scale-lib-1.1.2.jar",
    "third-party/java/astyanax/joda-time-2.2.jar",
    "third-party/java/astyanax/libthrift-0.7.0.jar",
    "third-party/java/astyanax/log4j-1.2.16.jar",
    "third-party/java/astyanax/slf4j-api-1.7.2.jar",
    "third-party/java/astyanax/slf4j-log4j12-1.7.2.jar",
    "third-party/java/closure-templates/soy-excluding-deps.jar",
    "third-party/java/gson/gson-2.2.4.jar",
    "third-party/java/eclipse/org.eclipse.core.contenttype_3.4.200.v20130326-1255.jar",
    "third-party/java/eclipse/org.eclipse.core.jobs_3.5.300.v20130429-1813.jar",
    "third-party/java/eclipse/org.eclipse.core.resources_3.8.101.v20130717-0806.jar",
    "third-party/java/eclipse/org.eclipse.core.runtime_3.9.100.v20131218-1515.jar",
    "third-party/java/eclipse/org.eclipse.equinox.common_3.6.200.v20130402-1505.jar",
    "third-party/java/eclipse/org.eclipse.equinox.preferences_3.5.100.v20130422-1538.jar",
    "third-party/java/eclipse/org.eclipse.jdt.core_3.9.2.v20140114-1555.jar",
    "third-party/java/eclipse/org.eclipse.osgi_3.9.1.v20140110-1610.jar",
    "third-party/java/dd-plist/dd-plist.jar",
    "third-party/java/jetty/jetty-all-9.0.4.v20130625.jar",
    "third-party/java/jetty/servlet-api.jar",
    "third-party/java/xz-java-1.3/xz-1.3.jar",
    "third-party/java/commons-compress/commons-compress-1.8.1.jar",
]

RESOURCES = {
    "buck_server": "bin/buck",
    "buck_client": "build/ng",
    "log4j_config_file": "config/log4j.properties",

    "testrunner_classes": "build/testrunner/classes",
    "abi_processor_classes": "build/abi_processor/classes",
    "path_to_asm_jar": "third-party/java/asm/asm-debug-all-5.0.3.jar",
    "logging_config_file": "config/logging.properties",
    "path_to_buck_py": "src/com/facebook/buck/parser/buck.py",
    "path_to_pathlib_py": "third-party/py/pathlib/pathlib.py",
    "path_to_compile_asset_catalogs_py": (
        "src/com/facebook/buck/apple/compile_asset_catalogs.py"),
    "path_to_compile_asset_catalogs_build_phase_sh": (
        "src/com/facebook/buck/apple/compile_asset_catalogs_build_phase.sh"),
    "path_to_intellij_py": "src/com/facebook/buck/command/intellij.py",
    "path_to_python_test_main": "src/com/facebook/buck/python/__test_main__.py",
    "jacoco_agent_jar": "third-party/java/jacoco/jacocoagent.jar",
    "report_generator_jar": "build/report-generator.jar",
    "path_to_static_content": "webserver/static",
    "path_to_pex": "src/com/facebook/buck/python/pex.py",
    "quickstart_origin_dir": "src/com/facebook/buck/cli/quickstart/android",
    "dx": "third-party/java/dx-from-kitkat/etc/dx",
    "android_agent_path": "assets/android/agent.apk"
}


class BuckRepo(BuckTool):

    def __init__(self, buck_bin_dir, buck_project):
        super(BuckRepo, self).__init__(buck_project)

        self._buck_dir = self._platform_path(os.path.dirname(buck_bin_dir))
        self._build_success_file = os.path.join(
            self._buck_dir, "build", "successful-build")

        dot_git = os.path.join(self._buck_dir, '.git')
        self._is_git = os.path.exists(dot_git) and os.path.isdir(dot_git) and which('git') and \
            sys.platform != 'cygwin'
        self._is_buck_repo_dirty_override = os.environ.get('BUCK_REPOSITORY_DIRTY')

        buck_version = buck_project.buck_version
        if self._is_git and not buck_project.has_no_buck_check and buck_version:
            revision = buck_version[0]
            branch = buck_version[1] if len(buck_version) > 1 else None
            self._checkout_and_clean(revision, branch)

        self._build()

    def _checkout_and_clean(self, revision, branch):
        with Tracing('BuckRepo._checkout_and_clean'):
            if not self._revision_exists(revision):
                print(textwrap.dedent("""\
                    Required revision {0} is not
                    available in the local repository.
                    Buck is fetching updates from git. You can disable this by creating
                    a '.nobuckcheck' file in your repository, but this might lead to
                    strange bugs or build failures.""".format(revision)),
                      file=sys.stderr)
                git_command = ['git', 'fetch']
                git_command.extend(['--all'] if not branch else ['origin', branch])
                try:
                    subprocess.check_call(
                        git_command,
                        stdout=sys.stderr,
                        cwd=self._buck_dir)
                except subprocess.CalledProcessError:
                    raise BuckToolException(textwrap.dedent("""\
                          Failed to fetch Buck updates from git."""))

            current_revision = self._get_git_revision()

            if current_revision != revision:
                print(textwrap.dedent("""\
                    Buck is at {0}, but should be {1}.
                    Buck is updating itself. To disable this, add a '.nobuckcheck'
                    file to your project root. In general, you should only disable
                    this if you are developing Buck.""".format(
                    current_revision, revision)),
                    file=sys.stderr)

                try:
                    subprocess.check_call(
                        ['git', 'checkout', '--quiet', revision],
                        cwd=self._buck_dir)
                except subprocess.CalledProcessError:
                    raise BuckToolException(textwrap.dedent("""\
                          Failed to update Buck to revision {0}.""".format(revision)))
                if os.path.exists(self._build_success_file):
                    os.remove(self._build_success_file)

                ant = self._check_for_ant()
                self._run_ant_clean(ant)
                raise RestartBuck()

    def _join_buck_dir(self, relative_path):
        return os.path.join(self._buck_dir, *(relative_path.split('/')))

    def _is_dirty(self):
        if self._is_buck_repo_dirty_override:
            return self._is_buck_repo_dirty_override == "1"

        if not self._is_git:
            return False

        output = check_output(
            ['git', 'status', '--porcelain'],
            cwd=self._buck_dir)
        return bool(output.strip())

    def _has_local_changes(self):
        if not self._is_git:
            return False

        output = check_output(
            ['git', 'ls-files', '-m'],
            cwd=self._buck_dir)
        return bool(output.strip())

    def _get_git_revision(self):
        if not self._is_git:
            return 'N/A'

        output = check_output(
            ['git', 'rev-parse', 'HEAD', '--'],
            cwd=self._buck_dir)
        return output.splitlines()[0].strip()

    def _get_git_commit_timestamp(self):
        if self._is_buck_repo_dirty_override or not self._is_git:
            return -1

        return check_output(
            ['git', 'log', '--pretty=format:%ct', '-1', 'HEAD', '--'],
            cwd=self._buck_dir).strip()

    def _revision_exists(self, revision):
        returncode = subprocess.call(
            ['git', 'cat-file', '-e', revision],
            cwd=self._buck_dir)
        return returncode == 0

    def _check_for_ant(self):
        ant = which('ant')
        if not ant:
            message = "You do not have ant on your $PATH. Cannot build Buck."
            if sys.platform == "darwin":
                message += "\nTry running 'brew install ant'."
            raise BuckToolException(message)
        return ant

    def _print_ant_failure_and_exit(self, ant_log_path):
        print(textwrap.dedent("""\
                ::: 'ant' failed in the buck repo at '{0}',
                ::: and 'buck' is not properly built. It will be unusable
                ::: until the error is corrected. You can check the logs
                ::: at {1} to figure out what broke.""".format(
              self._buck_dir, ant_log_path)), file=sys.stderr)
        if self._is_git:
            raise BuckToolException(textwrap.dedent("""\
                ::: It is possible that running this command will fix it:
                ::: git -C "{0}" clean -xfd""".format(self._buck_dir)))
        else:
            raise BuckToolException(textwrap.dedent("""\
                ::: It is possible that running this command will fix it:
                ::: rm -rf "{0}"/build""".format(self._buck_dir)))

    def _run_ant_clean(self, ant):
        clean_log_path = os.path.join(self._buck_project.get_buck_out_log_dir(), 'ant-clean.log')
        with open(clean_log_path, 'w') as clean_log:
            exitcode = subprocess.call([ant, 'clean'], stdout=clean_log,
                                       cwd=self._buck_dir)
            if exitcode is not 0:
                self._print_ant_failure_and_exit(clean_log_path)

    def _run_ant(self, ant):
        ant_log_path = os.path.join(self._buck_project.get_buck_out_log_dir(), 'ant.log')
        with open(ant_log_path, 'w') as ant_log:
            exitcode = subprocess.call([ant], stdout=ant_log,
                                       cwd=self._buck_dir)
            if exitcode is not 0:
                self._print_ant_failure_and_exit(ant_log_path)

    def _compute_local_hash(self):
        git_tree_in = check_output(
            ['git', 'log', '-n1', '--pretty=format:%T', 'HEAD', '--'],
            cwd=self._buck_dir).strip()

        with EmptyTempFile(prefix='buck-git-index',
                           dir=self._tmp_dir) as index_file:
            new_environ = os.environ.copy()
            new_environ['GIT_INDEX_FILE'] = index_file.name
            subprocess.check_call(
                ['git', 'read-tree', git_tree_in],
                cwd=self._buck_dir,
                env=new_environ)

            subprocess.check_call(
                ['git', 'add', '-u'],
                cwd=self._buck_dir,
                env=new_environ)

            git_tree_out = check_output(
                ['git', 'write-tree'],
                cwd=self._buck_dir,
                env=new_environ).strip()

        with EmptyTempFile(prefix='buck-version-uid-input',
                           dir=self._tmp_dir,
                           closed=False) as uid_input:
            subprocess.check_call(
                ['git', 'ls-tree', '--full-tree', git_tree_out],
                cwd=self._buck_dir,
                stdout=uid_input)
            return check_output(
                ['git', 'hash-object', uid_input.name],
                cwd=self._buck_dir).strip()

    def _build(self):
        with Tracing('BuckRepo._build'):
            if not os.path.exists(self._build_success_file):
                print(
                    "Buck does not appear to have been built -- building Buck!",
                    file=sys.stderr)
                ant = self._check_for_ant()
                self._run_ant_clean(ant)
                self._run_ant(ant)
                open(self._build_success_file, 'w').close()

    def _has_resource(self, resource):
        return True

    def _get_resource(self, resource, exe=False):
        return self._join_buck_dir(RESOURCES[resource.name])

    def _get_buck_version_uid(self):
        with Tracing('BuckRepo._get_buck_version_uid'):
            if not self._is_git:
                return 'N/A'

            if not self._is_dirty():
                return self._get_git_revision()

            if (self._buck_project.has_no_buck_check or
                    not self._buck_project.buck_version):
                return self._compute_local_hash()

            if self._has_local_changes():
                print(textwrap.dedent("""\
                ::: Your buck directory has local modifications, and therefore
                ::: builds will not be able to use a distributed cache.
                ::: The following files must be either reverted or committed:"""),
                      file=sys.stderr)
                subprocess.call(
                    ['git', 'ls-files', '-m'],
                    stdout=sys.stderr,
                    cwd=self._buck_dir)
            elif os.environ.get('BUCK_CLEAN_REPO_IF_DIRTY') != 'NO':
                print(textwrap.dedent("""\
                ::: Your local buck directory is dirty, and therefore builds will
                ::: not be able to use a distributed cache."""), file=sys.stderr)
                if sys.stdout.isatty():
                    print(
                        "::: Do you want to clean your buck directory? [y/N]",
                        file=sys.stderr)
                    choice = raw_input().lower()
                    if choice == "y":
                        subprocess.call(
                            ['git', 'clean', '-fd'],
                            stdout=sys.stderr,
                            cwd=self._buck_dir)
                        raise RestartBuck()

            return self._compute_local_hash()

    def _get_extra_java_args(self):
        return [
            "-Dbuck.git_commit={0}".format(self._get_git_revision()),
            "-Dbuck.git_commit_timestamp={0}".format(
                self._get_git_commit_timestamp()),
            "-Dbuck.git_dirty={0}".format(int(self._is_dirty())),
        ]

    def _get_bootstrap_classpath(self):
        return self._join_buck_dir("build/bootstrapper/classes")

    def _get_java_classpath(self):
        return self._pathsep.join([self._join_buck_dir(p) for p in JAVA_CLASSPATHS])


class EmptyTempFile(object):

    def __init__(self, prefix=None, dir=None, closed=True):
        self.file, self.name = tempfile.mkstemp(prefix=prefix, dir=dir)
        if closed:
            os.close(self.file)
        self.closed = closed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        os.remove(self.name)

    def close(self):
        if not self.closed:
            os.close(self.file)
        self.closed = True

    def fileno(self):
        return self.file
