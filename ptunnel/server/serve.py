import threading
import socket
import time
import random
import os
import ssl
from pathlib import Path
from hashlib import sha256
from flask import Flask, request
from flask_cors import CORS

from Crypto.PublicKey import RSA

import ptunnel

app = Flask(__name__)
CORS(app)

session = {}

def checker(port):
    # check that local port is not in use
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("0.0.0.0", port))
        s.close()
    except OSError:
        return False
    return True

def looper():
    while True:
        loop_checker_port()
        loop_checker_session()
        time.sleep(12)

def loop_checker_port():
    for session_id in session:
        for port in session[session_id]["ports"]:
            if checker(port):
                session[session_id]["ports"].remove(port)
                ptunnel.logger.info(f"Port {port} is released from team {session[session_id]['id']}.")
                return

def loop_checker_session():
    for session_id in session:
        if time.time() - session[session_id]["updated"] > ptunnel.config.keepalive:
            print(session[session_id])
            del session[session_id]
            ptunnel.logger.info(f"Session {session_id} is expired.")
            return

def create_sessid():
    return sha256(str(time.time()).encode()).hexdigest()

def new_key():
    key = RSA.generate(4096)
    private_key = key.export_key()
    public_key = key.publickey().exportKey('OpenSSH')

    return private_key, public_key

def add_key(session_id: str, key: str):
    # check user exists
    user = session[session_id]["id"]
    sshPath = Path(f"/home/A{user}/.ssh/")
    sshakPath = Path(f"/home/A{user}/.ssh/authorized_keys")
    if not os.path.exists(f"/home/{user}/.ssh"):
        os.system(f"useradd -m A{user} -s /sbin/nologin")
        sshPath.mkdir(exist_ok=True)
        sshakPath.touch(exist_ok=True)
        os.system(f"chown A{user}:A{user} /home/A{user}/.ssh")
        os.system(f"chown A{user}:A{user} /home/A{user}/.ssh/authorized_keys")
        sshPath.chmod(0o700)
        sshakPath.chmod(0o600)
    
    # add key
    sshakPath.write_text(f"{sshakPath.read_text()}no-X11-forwarding,no-agent-forwarding,no-pty,command=\"echo 'This account can only be used for port forwarding.'\" " + key + "\n")
    return

@app.route("/auth", methods=["POST"])
def auth():
    data = request.json
    if "id" not in data or "password" not in data:
        return {"error": "Invalid request."}, 400
    if data["password"] != ptunnel.config.password:
        return {"error": "Invalid password."}, 401
    
    session_id = create_sessid()
    session[session_id] = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated": time.time(),
        "id": data["id"],
        "ports": [],
    }

    return {"session_id": session_id}, 200

@app.route("/keepalive", methods=["POST"])
def keepalive():
    data = request.json
    if "session_id" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    
    session[data["session_id"]]["updated"] = time.time()

    return {"status": "ok"}, 200

@app.route("/forward", methods=["POST"])
def forward():
    data = request.json
    if "session_id" not in data or "port" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    
    while True:
        port = random.randint(ptunnel.config.range["start"], ptunnel.config.range["end"])
        if checker(port):
            break
    
    ptunnel.logger.info(f"Port {port} is now used for {session[data['session_id']]}.")

    return {"status": "ok", "port": port}, 200

@app.route("/release", methods=["POST"])
def release():
    data = request.json
    if "session_id" not in data or "port" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    if data["port"] not in session[data["session_id"]]["ports"]:
        return {"error": "Port not found."}, 404
    
    session[data["session_id"]]["ports"].remove(data["port"])
    ptunnel.logger.info(f"Port {data['port']} is released.")

    return {"status": "ok"}, 200

@app.route("/closeall", methods=["POST"])
def closeall():
    data = request.json
    if "session_id" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    
    for port in session[data["session_id"]]["ports"]:
        session[data["session_id"]]["ports"].remove(port)
        ptunnel.logger.info(f"Port {port} is released.")

    return {"status": "ok"}, 200

@app.route("/make_key", methods=["POST"])
def make_key():
    data = request.json
    if "session_id" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401

    private_key, public_key = new_key()
    add_key(data["session_id"], public_key.decode())

    return {"private_key": private_key.decode(), "public_key": public_key.decode()}, 200

@app.route("/logout", methods=["POST"])
def logout():
    data = request.json
    if "session_id" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    
    del session[data["session_id"]]

    return {"status": "ok"}, 200

def run():
    worker = threading.Thread(target=looper, daemon=True)
    worker.start()

    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(ptunnel.config.ssl["cert"], ptunnel.config.ssl["key"])
    app.run(host="0.0.0.0", port=443, ssl_context=ssl_context)
