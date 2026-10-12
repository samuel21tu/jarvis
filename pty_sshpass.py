#!/usr/bin/env python3
# ==============================================================================
# JARVIS NEXUS // EXECUTOR PTY DE SSH/SCP COM INJEÇÃO SEGURA DE SENHA
# Gerencia conexões e transferências para o servidor casaos sem necessidade de sshpass binário.
# ==============================================================================

import os
import pty
import sys

def execute_pty(password: str, command: list) -> int:
    """
    Executa o comando fornecido em um pseudo-terminal (PTY) dedicado.
    Injeta a senha automaticamente quando o prompt de autenticação for detectado
    e redireciona a saída em tempo real para o stdout do processo pai.
    """
    pid, fd = pty.fork()
    if pid == 0:
        # Processo filho: substitui a imagem do processo pelo comando alvo
        try:
            os.execvp(command[0], command)
        except Exception as e:
            sys.stderr.write(f"Erro ao executar o comando {command[0]}: {e}\n")
            sys.exit(127)
    else:
        # Processo pai: monitora a saída do terminal e injeta credenciais
        password_attempts = 0
        max_attempts = 3

        while True:
            try:
                data = os.read(fd, 1024)
                if not data:
                    break
                
                # Transmite saída ao vivo no terminal
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()

                data_lower = data.lower()

                # Responde automaticamente à confirmação de fingerprint/host key se solicitado
                if b"yes/no" in data_lower:
                    os.write(fd, b"yes\n")

                # Detecta prompt de autenticação por senha
                if (b"password:" in data_lower or b"senha:" in data_lower or b"assword" in data_lower) and password_attempts < max_attempts:
                    os.write(fd, password.encode() + b"\n")
                    password_attempts += 1

            except OSError:
                break

        # Captura o status de finalização do processo filho
        _, status = os.waitpid(pid, 0)
        if hasattr(os, "waitstatus_to_exitcode"):
            return os.waitstatus_to_exitcode(status)
        return (status >> 8) if os.WIFEXITED(status) else 1

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 pty_sshpass.py <senha> <comando> [argumentos...]")
        sys.exit(1)

    auth_password = sys.argv[1]
    cmd_args = sys.argv[2:]
    exit_status = execute_pty(auth_password, cmd_args)
    sys.exit(exit_status)
