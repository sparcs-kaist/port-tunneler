import requests
from subprocess import Popen, PIPE
from pathlib import Path
from threading import Thread
import time

import ptunnel

keepalive_thread = None
team_id = None
SRV_URL = "htunnel.sparcs.net"
sessid = None
logger = ptunnel.logger
sshworkers = {}

def _kill_port(port: int):
    if port in sshworkers:
        sshworkers[port]["worker"].terminate()
        del sshworkers[port]
    return

def _request(url, json, keepalive=False, timeout=5):
    global sessid

    if not sessid:
        logger.error("Not logged in.")
        return False

    try:
        json.update({"session_id": sessid})
        response = requests.post(f"https://{SRV_URL}/{url}", json=json, timeout=timeout)
        if response.status_code == 401:
            for port in sshworkers:
                sshworkers[port]["worker"].terminate()
            logger.error(f"Error: Unauthorized.")
            if keepalive: raise Exception("Unauthorized.")
            exit(2)
        if response.status_code != 200:
            logger.error(f"Error: {response.json()['error']}")
            if keepalive: raise Exception(response.json())
            return False
        data = response.json()
        if keepalive and "kick" in data:
            _kill_port(data["kick"])
            logger.info(f"Port {data['kick']} is closed by server.")
            return
        return data
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Please contact admin.")
        exit(1)

def _setup():
    global sessid
    if not sessid:
        logger.error("Not logged in.")
        return False
    
    sshPath = Path(f"/home/elicer/.ssh/")
    sshidPath = sshPath / "id_rsa"

    if not sshPath.exists():
        sshPath.mkdir(exist_ok=True)
        sshPath.chmod(0o700)
    if not sshidPath.exists():
        rtn = _request("make_key", {}, timeout=15)
        if not rtn:
            return False
        sshidPath.write_text(rtn["private_key"])
        sshidPath.chmod(0o600)
    
    keepalive_thread = Thread(target=keepalive, daemon=True)
    keepalive_thread.start()

    return True

def forward(args: list):
    if not args:
        logger.error("Invalid port.")
        return
    
    port = int(args[0])
    if not port:
        logger.error("Invalid port.")
        return
    
    rtn = _request("forward", {"port": port})
    if not rtn:
        return
    remoteport = rtn["port"]
    
    logger.info(f"Opening port {port}...")
    command = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "GatewayPorts=yes",
        "-N",
        "-R",
        f"0.0.0.0:{remoteport}:localhost:{port}",
        f"{SRV_URL}",
        f"-l",
        f"A{team_id}",
    ]

    sshworkers[port] = {
        "worker": Popen(command, stdout=PIPE, stderr=PIPE),
        "remoteport": remoteport,
    }
    logger.info(f"Port {port} is now open. Connect to {SRV_URL}:{remoteport}.")
    return

def _exit(args: list):
    _request("logout", {})
    for port in sshworkers:
        sshworkers[port]["worker"].terminate()
    
    exit(0)

def lists(args: list):
    logger.info("Open ports:")
    for port in sshworkers:
        logger.info(f"  {SRV_URL}:{sshworkers[port]['remoteport']} -> localhost:{port}")
        if "domain" in sshworkers[port]:
            logger.info(f"  https://{sshworkers[port]['domain']}/ -> localhost:{port}")
    logger.info("End of list.")
    return

def domainmap(args: list):
    if not args:
        logger.error("Invalid domain.")
        return
    if len(args) < 2:
        logger.error("Invalid domain.")
        return
    
    domain = args[0]
    port = int(args[1])
    if "." in domain:
        logger.error("Invalid domain.")
        return

    if port not in sshworkers:
        logger.error(f"Port {port} is not open.")
        return
    
    if "domain" in sshworkers[port]:
        logger.error(f"Domain {sshworkers[port]['domain']} is already mapped.")
        return
    
    rtn = _request("domainmap", {"domain": domain, "port": sshworkers[port]["remoteport"]})
    if not rtn:
        return
    domain = rtn["domain"]

    sshworkers[port]["domain"] = domain

    logger.info(f"Domain https://{domain}/ is now mapped to port localhost:{port}.")
    return

def close(args: list):
    if not args:
        logger.error("Invalid port.")
        return

    port = int(args[0])
    if not port:
        logger.error("Invalid port.")
        return
    
    if port not in sshworkers:
        logger.error(f"Port {port} is not open.")
        return
    
    rtn = _request("close", {"port": port})
    sshworkers[port]["worker"].terminate()
    del sshworkers[port]
    logger.info(f"Port {port} is closed.")
    return

def help(args: list):
    logger.info("Available commands:")
    logger.info("  forward <port>: Open a port.")
    logger.info("  domainmap <domain> <port>: Map a domain to a port.")
    logger.info("     (e.g. domainmap example 30000 -> https://example.hackaton.sparcs.net/ -> localhost:30000)")
    logger.info("  close <port>: Close a port.")
    logger.info("  lists: List open ports.")
    logger.info("  exit: Exit the program.")

def keepalive():
    while True:
        try:
            _request("keepalive", {})
        except:
            logger.error("Closing all connections.")
            for port in sshworkers:
                sshworkers[port]["worker"].terminate()
        time.sleep(5)

def run():
    global sessid
    global team_id

    while True:
        logger.info("Enter your team ID. (e.g. A99)")
        team_id = input("> ")
        logger.info("Please enter the password.")
        password = input("> ")
        if not password:
            logger.error("Password cannot be empty.")
            continue

        try:
            response = requests.post(f"https://{SRV_URL}/auth", json={"id": team_id, "password": password}, timeout=5)
            if response.status_code != 200:
                logger.error(f"Error: {response.json()['error']}")
                continue
            sessid = response.json()["session_id"]
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            logger.error("Please contact admin.")
            exit(1)
    
    _setup()
    logger.info("Successfully logged in.")
    logger.info("Command \"help\" for help.")

    while True:
        command = input("> ")
        command_first = command.split(" ")[0]
        if command_first.startswith("_"):
            logger.error("Command not found.")
            continue
        if command_first in globals():
            globals()[command_first](command.split(" ")[1:])
        elif command_first == "exit":
            _exit(command.split(" ")[1:])
        else:
            logger.error("Command not found.")
            continue