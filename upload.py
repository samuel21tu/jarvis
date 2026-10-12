import paramiko
import os

host = '192.168.1.92'
user = 'server'
password = '$samuca123$'

local_file = 'deploy.tar.gz'
remote_dir = '/home/server/jarvis'
remote_file = f'{remote_dir}/deploy.tar.gz'

print("Conectando SSH...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password)

print("Transferindo arquivo...")
sftp = ssh.open_sftp()
sftp.put(local_file, remote_file)
sftp.close()

print("Extraindo e reiniciando...")
stdin, stdout, stderr = ssh.exec_command(f'cd {remote_dir} && tar xzf deploy.tar.gz && docker compose up -d --build || docker-compose up -d --build')
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())

ssh.close()
print("Deploy completo.")
