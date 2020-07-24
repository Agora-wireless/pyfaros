import paramiko
import scp

class RunCommandFailed(Exception):
    def __init__(self, cmd, errors):
        message = "Failed cmd: {0}\nstderr:{1}\n".format(cmd, errors)
        super(RunCommandFailed, self).__init__(message)

class EasySsh(object):
    def __init__(self, name, remote_ipaddr, user, password):
        self.name = name or remote_ipaddr
        self.remote_ipaddr = remote_ipaddr
        self.user = user
        self.password = password
        self.connect()
        self.scp_client = None

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.remote_ipaddr, username=self.user, password=self.password)

    def getScpClient(self):
        if self.scp_client is None:
            self.client_for_scp = paramiko.SSHClient()
            self.client_for_scp.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client_for_scp.connect(self.remote_ipaddr, username=self.user, password=self.password)
            self.scp_client = scp.SCPClient(self.client_for_scp.get_transport())
        return self.scp_client

    def copyFile(self, filename, dst):
        self.getScpClient().put(filename, dst)

    def runCommand(self, *args, sudo=False):
        channel = self.client.get_transport().open_session()

        cmd = ' '.join(args)
        if sudo:
            cmd = 'sudo --stdin ' + cmd

        channel.exec_command(cmd)
        stdin = channel.makefile_stdin('w')
        stderr = channel.makefile_stderr()
        stdout = channel.makefile()
        if sudo:
            stdin.write(self.password+'\n')

        errors = '\n'.join(line.strip('\n') for line in stderr)
        exit_status = channel.recv_exit_status()
        if exit_status:
            self.exit_status = exit_status
            raise RunCommandFailed(cmd, errors)

        return '\n'.join(line.strip('\n') for line in stdout)
