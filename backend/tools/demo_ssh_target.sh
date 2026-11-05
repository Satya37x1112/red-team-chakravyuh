#!/usr/bin/env bash
# Deliberately-vulnerable SSH demo target for the BruteForce lab (like demo_site.py
# is for the DDoS lab). Stands up an OpenSSH server inside WSL with ONE throwaway
# account whose password is intentionally weak and present in the demo wordlist,
# so Hydra can demonstrate a successful credential-guess against it.
#
# Everything here is a disposable lab account on localhost inside WSL — it is not a
# real user, it does not touch the Windows login, and it only listens on 127.0.0.1.
# Authorized, isolated-lab use only. Run as root inside WSL:
#     sudo bash demo_ssh_target.sh [port] [username] [password]
set -uo pipefail

PORT="${1:-5000}"                 # listen port (demo runs on 5000, not 22)
USER_NAME="${2:-labadmin}"        # must also appear in tools/users.txt
USER_PASS="${3:-Welcome1}"        # must also appear in tools/passwords.txt (weak on purpose)

echo "[*] Ensuring DNS so apt can reach the archive..."
if ! getent hosts archive.ubuntu.com >/dev/null 2>&1; then
  printf 'nameserver 8.8.8.8\nnameserver 1.1.1.1\n' > /etc/resolv.conf
fi

echo "[*] Installing openssh-server (if missing)..."
if ! command -v sshd >/dev/null 2>&1 && ! [ -x /usr/sbin/sshd ]; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server >/dev/null
fi

echo "[*] Creating throwaway lab account '${USER_NAME}' with a weak demo password..."
id "${USER_NAME}" >/dev/null 2>&1 || useradd -m -s /bin/bash "${USER_NAME}"
echo "${USER_NAME}:${USER_PASS}" | chpasswd

echo "[*] Enabling password auth and pinning the listen port to ${PORT}..."
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
grep -q '^PasswordAuthentication yes' /etc/ssh/sshd_config || echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config
# Bind to the demo port on localhost only.
sed -i '/^#\?Port /d; /^ListenAddress /d' /etc/ssh/sshd_config
printf 'Port %s\nListenAddress 127.0.0.1\n' "${PORT}" >> /etc/ssh/sshd_config
mkdir -p /run/sshd
ssh-keygen -A >/dev/null 2>&1

echo "[*] (Re)starting sshd..."
service ssh restart >/dev/null 2>&1 || { pkill -f "sshd" 2>/dev/null; /usr/sbin/sshd; }

sleep 1
if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
  echo "[+] SSH demo target UP on 127.0.0.1:${PORT}  (lab account: ${USER_NAME} / ${USER_PASS})"
else
  echo "[!] sshd not listening on :${PORT} — check 'service ssh status' / 'journalctl -u ssh'"
  exit 1
fi
