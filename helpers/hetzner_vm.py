import os
import time
import paramiko
import requests
import logging
import socket
from datetime import datetime, timezone

logger = logging.getLogger("my_app_logger")

HETZNER_API_TOKEN = os.environ.get("HETZNER_API_TOKEN")
HETZNER_SSH_KEY_ID = os.environ.get("HETZNER_SSH_KEY_ID")
HETZNER_SNAPSHOT_ID = os.environ.get(
    "HETZNER_SNAPSHOT_ID"
)  # Your lotus3 snapshot
SSH_PRIVATE_KEY = os.environ.get(
    "HETZNER_SSH_PRIVATE_KEY_IN_DOCKER", "~/.ssh/id_rsa"
)
# Optional, all unset by default (VMs are then created as before).
# See docs/hetzner_remote_pipeline.md, "Private network to production".
HETZNER_LOCATION = os.environ.get("HETZNER_LOCATION")  # e.g. hel1
HETZNER_NETWORK_ID = os.environ.get("HETZNER_NETWORK_ID")
HETZNER_FIREWALL_ID = os.environ.get("HETZNER_FIREWALL_ID")
# "1": connect to the VM over the private network instead of its public IPv4
HETZNER_SSH_VIA_PRIVATE_IP = (
    os.environ.get("HETZNER_SSH_VIA_PRIVATE_IP") == "1"
)

API_URL = "https://api.hetzner.cloud/v1/servers"


class HetznerVMError(Exception):
    pass


# ---------------------------------------------------------
#                 API Helpers
# ---------------------------------------------------------
def _api_headers():
    return {"Authorization": f"Bearer {HETZNER_API_TOKEN}"}


def create_vm(name="lotus3-runner", server_size="cpx62"):
    """Create a VM from snapshot."""
    data = {
        "name": name,
        "server_type": server_size,
        "image": HETZNER_SNAPSHOT_ID,
        "ssh_keys": [HETZNER_SSH_KEY_ID],
    }
    if HETZNER_LOCATION:
        data["location"] = HETZNER_LOCATION
    if HETZNER_NETWORK_ID:
        data["networks"] = [int(HETZNER_NETWORK_ID)]
    if HETZNER_FIREWALL_ID:
        data["firewalls"] = [{"firewall": int(HETZNER_FIREWALL_ID)}]

    r = requests.post(API_URL, json=data, headers=_api_headers())
    if r.status_code != 201:
        raise HetznerVMError(f"VM create failed: {r.text}")

    server = r.json()["server"]
    ip = server["public_net"]["ipv4"]["ip"]

    if HETZNER_NETWORK_ID and HETZNER_SSH_VIA_PRIVATE_IP:
        try:
            ip = _wait_for_private_ip(server["id"])
        except Exception:
            # The caller only cleans up VMs it got back, so delete it here.
            delete_vm(server["id"])
            raise

    return {"id": server["id"], "ip": ip}


def _wait_for_private_ip(server_id, timeout_seconds=120):
    """Wait for the VM's IP on HETZNER_NETWORK_ID and return it."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        r = requests.get(f"{API_URL}/{server_id}", headers=_api_headers())
        if r.status_code == 200:
            for net in r.json()["server"].get("private_net", []):
                same_net = str(net.get("network")) == str(HETZNER_NETWORK_ID)
                if same_net and net.get("ip"):
                    return net["ip"]
        time.sleep(5)
    raise HetznerVMError(
        f"VM {server_id} got no IP on network {HETZNER_NETWORK_ID} "
        f"within {timeout_seconds}s."
    )


def delete_vm(server_id):
    """Delete a VM."""
    r = requests.delete(f"{API_URL}/{server_id}", headers=_api_headers())
    if r.status_code not in [200, 202]:
        raise HetznerVMError(f"VM deletion failed: {r.text}")
    return True


# ---------------------------------------------------------
#            SSH Connection Helpers
# ---------------------------------------------------------
def _get_ssh_client(ip, timeout=10):
    key = paramiko.RSAKey.from_private_key_file(
        os.path.expanduser(SSH_PRIVATE_KEY)
    )

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        ip,
        username="root",
        pkey=key,
        timeout=timeout,
    )
    return ssh


def wait_for_ssh(ip, timeout_minutes=15, check_interval=30):
    """
    Wait until SSH becomes reachable on the VM.

    Non-blocking approach: first check TCP port 22, then attempt SSH handshake.
    Logs progress less often.
    """
    deadline = time.time() + timeout_minutes * 60
    last_log_time = 0

    while time.time() < deadline:
        try:
            # Quick TCP check
            sock = socket.create_connection((ip, 22), timeout=5)
            sock.close()

            # Try SSH handshake
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            key = paramiko.RSAKey.from_private_key_file(
                os.path.expanduser(SSH_PRIVATE_KEY)
            )
            ssh.connect(ip, username="root", pkey=key, timeout=10)
            ssh.close()

            logger.info(f"VM {ip} is ready for SSH.")
            return True

        except (socket.error, paramiko.SSHException) as e:
            now = time.time()
            if now - last_log_time >= check_interval:
                logger.warning(f"VM not ready yet ({ip}): {e}")
                last_log_time = now

            time.sleep(5)

        except Exception as e:
            now = time.time()
            if now - last_log_time >= check_interval:
                logger.warning(
                    f"Unexpected error while waiting for SSH ({ip}): {e}"
                )
                last_log_time = now
            time.sleep(5)

    raise HetznerVMError(
        f"SSH did not become available for VM {ip} in {timeout_minutes} minutes."
    )


def run_remote_command(ip, command, stream_output=False):
    """
    Execute a command via SSH on the VM.
    Returns stdout, stderr, exit_code.
    """

    ssh = _get_ssh_client(ip)
    stdin, stdout, stderr = ssh.exec_command(command)

    if stream_output:
        for line in iter(stdout.readline, ""):
            print(line, end="")

    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()

    ssh.close()
    return out, err, exit_code


# ---------------------------------------------------------
#             High-level Combined Runner
# ---------------------------------------------------------
VM_SHARE_MOUNTS = ["/mnt/seq_processed", "/mnt/lotus2_files"]


def ensure_shares_mounted(ip, attempts=12, delay_seconds=5):
    """
    Mount any share from the VM's fstab that isn't mounted yet, retrying
    while the network comes up. Raises HetznerVMError if they can't be
    mounted, so lotus3 never runs against empty folders.
    """
    mounts = " ".join(VM_SHARE_MOUNTS)
    # Wait until boot has finished (Docker and networking are up). It ends
    # as "degraded" if a boot-time mount failed, which is fine here.
    run_remote_command(ip, "timeout 300 systemctl is-system-running --wait")
    command = (
        f"for i in $(seq 1 {attempts}); do "
        f"ok=1; "
        f"for m in {mounts}; do "
        f"mountpoint -q $m || mount $m || ok=0; "
        f"done; "
        f'[ "$ok" = 1 ] && exit 0; '
        f"sleep {delay_seconds}; "
        f"done; "
        f"exit 1"
    )
    stdout, stderr, code = run_remote_command(ip, command)
    if code != 0:
        raise HetznerVMError(
            f"Could not mount the shares ({mounts}) on VM {ip}: "
            f"{stderr.strip() or stdout.strip()}"
        )
    logger.info(f"Shares mounted on VM {ip}.")


def run_lotus3_on_vm(command_string, server_name, server_size="cpx62"):
    """
    Main high-level function used by lotus2.py:
    - Creates VM
    - Waits until ready
    - Runs lotus3 command inside that VM
    - Deletes VM
    - Returns results
    """

    vm = create_vm(server_name, server_size)
    vm_id = vm["id"]
    vm_ip = vm["ip"]

    # On VMs, temporary files go to the VM's local disk. LotuS3 3.14+ refuses
    # top-level folders such as /tmp, so use the folder lotus2.py creates
    # (and points TMPDIR to) for remote runs.
    command_string = f"{command_string} -tmp /tmp/lotus_tmp"

    try:
        # 1. Wait for VM
        wait_for_ssh(vm_ip)

        # 2. Make sure the shares are mounted. At boot, the fstab mounts can
        # run before the private network reaches production, and then fail.
        ensure_shares_mounted(vm_ip)

        # 3. Run lotus3 command
        full_cmd = f"""
            docker run --rm \
                --user root \
                -v /mnt/seq_processed:/seq_processed \
                -v /mnt/lotus2_files:/lotus2_files \
                sequencing-submission-form-lotus3:latest \
                bash -c "{command_string}"
        """

        stdout, stderr, code = run_remote_command(vm_ip, full_cmd)

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": code,
            "vm_id": vm_id,
            "vm_ip": vm_ip,
        }

    finally:
        logger.info(f"Deleting the VM with id {vm_id}")
        delete_vm(vm_id)


def list_existing_vms():
    """
    List all existing Hetzner VMs with ID, name, creation date, and public IP.

    Returns:
        List[dict]: Each dict contains 'id', 'name', 'created', 'ip'
    """
    r = requests.get(API_URL, headers=_api_headers())
    if r.status_code != 200:
        raise HetznerVMError(f"Failed to list VMs: {r.text}")

    servers = r.json().get("servers", [])
    vm_list = []

    for srv in servers:
        vm_list.append(
            {
                "id": srv["id"],
                "name": srv["name"],
                "created": srv["created"],  # ISO 8601 timestamp
                "ip": (
                    srv["public_net"]["ipv4"]["ip"]
                    if "public_net" in srv
                    else None
                ),
            }
        )

    return vm_list


def send_vm_status_to_slack():
    from helpers.slack import send_message_to_slack

    vms = list_existing_vms()

    if not vms:
        # send_message_to_slack("No active Hetzner VMs found.")
        return

    message_lines = [":satellite: *Active Hetzner VMs:*"]

    now = datetime.now(timezone.utc)

    for vm in vms:
        created = datetime.fromisoformat(vm["created"].replace("Z", "+00:00"))
        uptime = now - created

        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        uptime_str = f"{days}d {hours}h {minutes}m"

        message_lines.append(
            f"- `ID {vm['id']}` | *{vm['name']}* | IP `{vm['ip']}` | Uptime: `{uptime_str}`"
        )

    final_message = "\n".join(message_lines)

    send_message_to_slack(final_message)
