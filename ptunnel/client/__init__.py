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
timeout = 5
logger = ptunnel.logger
sshworkers = {}

def _request(url, json):
    global sessid

    if not sessid:
        logger.error("Not logged in.")
        return False

    try:
        json.update({"session_id": sessid})
        response = requests.post(f"https://{SRV_URL}/{url}", json=json, timeout=timeout)
        if response.status_code != 401:
            for port in sshworkers:
                sshworkers[port]["worker"].terminate()
            logger.error(f"Error: Unauthorized.")
            exit(2)
        if response.status_code != 200:
            logger.error(f"Error: {response.json()['error']}")
            return False
        return response.json()
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Please contact admin.")
        exit(1)

def _setup():
    global sessid
    if not sessid:
        logger.error("Not logged in.")
        return False
    
    sshPath = Path(f"~/.ssh/")
    sshidPath = Path(f"~/.ssh/id_rsa")

    if not sshPath.exists():
        sshPath.mkdir(exist_ok=True)
        sshPath.chmod(0o700)
    if not sshidPath.exists():
        rtn = _request("new_key", {})
        if not rtn:
            return False
        sshidPath.write_text(rtn["private_key"])
        sshidPath.chmod(0o600)
    
    keepalive_thread = Thread(target=keepalive, daemon=True)
    keepalive_thread.start()

    return True

def forward(args: list):
    global sessid

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
    logger.info("End of list.")
    return



def close(args: list):
    global sessid

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

def help():
    logger.info("Available commands:")
    logger.info("  forward <port>: Open a port.")
    logger.info("  close <port>: Close a port.")
    logger.info("  lists: List open ports.")
    logger.info("  exit: Exit the program.")

def keepalive():
    while True:
        _request("keepalive", {})
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
            response = requests.post(f"https://{SRV_URL}/login", json={"id": team_id, "password": password}, timeout=timeout)
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