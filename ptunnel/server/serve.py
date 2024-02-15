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
from werkzeug.middleware.proxy_fix import ProxyFix
from Crypto.PublicKey import RSA

import ptunnel

app = Flask(__name__)
CORS(app)

session = {}
domainmapper: dict[int, str] = {}
kicklist: dict[str, list[int]] = {}

# proxyfix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

nginxconfPath = Path("/etc/nginx/ptunnel/")
NGINXCONF = """
server {
    server_name {srvdomain};
    
    include /etc/nginx/default.d/*.conf;

    location / {
        proxy_pass http://localhost:{port}/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/{tunneldns}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{tunneldns}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; 
}
server {
    if ($host = {srvdomain}) {
        return 301 https://$host$request_uri;
    } # managed by Certbot

    server_name {srvdomain}

    listen 80;
    return 404; # managed by Certbot
}
"""

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
        os.system(f"useradd -m A{user} -s /usr/sbin/nologin")
        sshPath.mkdir(exist_ok=True)
        sshakPath.touch(exist_ok=True)
        os.system(f"chown A{user}:A{user} /home/A{user}/.ssh")
        os.system(f"chown A{user}:A{user} /home/A{user}/.ssh/authorized_keys")
        sshPath.chmod(0o700)
        sshakPath.chmod(0o600)
    
    # add key
    sshakPath.write_text(f"{sshakPath.read_text()}no-X11-forwarding,no-agent-forwarding,no-pty,command=\"echo 'This account can only be used for port forwarding.'\" " + key + "\n")
    return

def release_port(port: int, session_id: str, kick=False):
    if port in domainmapper:
        domainPath = nginxconfPath / domainmapper[port]
        domainPath.unlink(missing_ok=True)
        domainmapper.pop(port)
    session[session_id]["ports"].remove(port)
    if kick: 
        if session_id not in kicklist:
            kicklist[session_id] = []
        kicklist[session_id].append(port)
    ptunnel.logger.info(f"Port {port} is released.")
    

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

    rtn = {"status": "ok"}

    session[data["session_id"]]["updated"] = time.time()
    if data["session_id"] in kicklist:
        ports = kicklist.pop(data["session_id"])
        if "kick" not in rtn:
            rtn["kick"] = []
        rtn["kick"].append(ports)

    return rtn, 200

@app.route("/forward", methods=["POST"])
def forward():
    data = request.json
    if "session_id" not in data or "port" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    
    while True:
        port = random.randint(ptunnel.config.range["start"], ptunnel.config.range["end"])
        session[data["session_id"]]["ports"].append(port)
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
    
    release_port(data["port"], data["session_id"])

    return {"status": "ok"}, 200

@app.route("/close", methods=["POST"])
def close():
    data = request.json
    if "session_id" not in data or "port" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    if data["port"] not in session[data["session_id"]]["ports"]:
        return {"error": "Port not found."}, 404

    release_port(data["port"], data["session_id"])

    return {"status": "ok"}, 200

@app.route("/closeall", methods=["POST"])
def closeall():
    global nginxconfPath
    data = request.json
    if "session_id" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    
    for port in session[data["session_id"]]["ports"]:
        release_port(port, data["session_id"])

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
    ptunnel.logger.info(f"Key is made for {session[data['session_id']]['id']}.")

    return {"private_key": private_key.decode(), "public_key": public_key.decode()}, 200

@app.route("/logout", methods=["POST"])
def logout():
    data = request.json
    if "session_id" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    
    for port in session[data["session_id"]]["ports"]:
        ptunnel.logger.info(f"Port {port} is released. (logout {session[data['session_id']]['id']})")
    ptunnel.logger.info(f"Session {session[data['session_id']]['id']} logged out.")
    del session[data["session_id"]]


    return {"status": "ok"}, 200

@app.route("/domainmap", methods=["POST"])
def domainmap():
    data = request.json
    if "session_id" not in data or "port" not in data or "domain" not in data:
        return {"error": "Invalid request."}, 400
    if data["session_id"] not in session:
        return {"error": "Unauthorized."}, 401
    if data["port"] not in session[data["session_id"]]["ports"]:
        return {"error": "Port not found."}, 404
    
    srvdomain = f"{data['domain']}.{ptunnel.config.tunneldns}"
    srvdomainconfPath = nginxconfPath / srvdomain

    if srvdomainconfPath.exists():
        return {"error": "Domain already exists."}, 400
    
    nginxconf = NGINXCONF.format(srvdomain=srvdomain, port=data["port"], tunneldns=ptunnel.config.tunneldns)
    srvdomainconfPath.write_text(nginxconf)
    nginxtry = os.system(f"nginx -t")
    if nginxtry != 0:
        srvdomainconfPath.unlink()
        ptunnel.logger.error(nginxconf)
        return {"error": "International server error. Contact admin."}, 500
    
    os.system("systemctl reload nginx")
    domainmapper.update({data["port"]: srvdomain})
    
    ptunnel.logger.info(f"Domain {srvdomain} with https is mapped to port {data['port']}.")
    
    return {"status": "ok"}, 200

def auth_admin(req):
    if "pass" not in req.args:
        return {"error": "Invalid request."}, 400
    if req.args["pass"] != ptunnel.config.adminpassword:
        return {"error": "Unauthorized."}, 401
    return {}, 200

@app.route("/manage/kick", methods=["GET"])
def kick():
    rtn, statuscode = auth_admin(request)
    if statuscode != 200: return rtn, statuscode

    if "session_id" not in request.args:
        return {"error": "Invalid request."}, 400
    if request.args["session_id"] not in session:
        return {"error": "Session not found."}, 404
    
    for port in session[request.args["session_id"]]["ports"]:
        release_port(port, request.args["session_id"], kick=True)

    return {"status": "ok"}, 200

@app.route("/manage/list", methods=["GET"])
def list():
    rtn, statuscode = auth_admin(request)
    if statuscode != 200: return rtn, statuscode

    return {"session": session, "domainmap": domainmapper}, 200

def run():
    cert = Path(f"/etc/letsencrypt/live/{ptunnel.config.tunneldns}/")
    if not cert.exists():
        ptunnel.logger.error(f"SSL certificate not found: {cert}")
        exit(1)
    
    if nginxconfPath.exists():
        os.system(f"rm -rf {nginxconfPath}")
    nginxconfPath.mkdir(exist_ok=True)

    worker = threading.Thread(target=looper, daemon=True)
    worker.start()
    app.run(host="0.0.0.0", port=5000)
