import os
import time
import uuid
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = os.getenv("BASE_URL", "https://localhost").rstrip("/")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "5"))

def session():
    s = requests.Session()
    s.verify = False  # para HTTPS adhoc/self-signed
    return s

def wait_until_up():
    s = session()
    url = f"{BASE_URL}/login.html"
    last_exc = None
    for _ in range(40):
        try:
            r = s.get(url, timeout=TIMEOUT)
            if r.status_code in (200, 302):
                return
        except Exception as e:
            last_exc = e
        time.sleep(0.5)
    raise RuntimeError(f"API no responde en {url}. Último error: {last_exc}")

def post_json(path, payload, headers=None):
    return session().post(f"{BASE_URL}{path}", json=payload, headers=headers or {}, timeout=TIMEOUT)

def get(path, headers=None):
    return session().get(f"{BASE_URL}{path}", headers=headers or {}, timeout=TIMEOUT)

def put_json(path, payload, headers=None):
    return session().put(f"{BASE_URL}{path}", json=payload, headers=headers or {}, timeout=TIMEOUT)

def delete(path, headers=None):
    return session().delete(f"{BASE_URL}{path}", headers=headers or {}, timeout=TIMEOUT)

def auth(token):
    return {"Authorization": f"Bearer {token}"}

def test_00_service_up():
    wait_until_up()

def test_10_register_edge_cases():
    r = post_json("/api/register", {"username": "admin", "password": "x"})
    assert r.status_code == 400

    r = post_json("/api/register", {"username": "", "password": ""})
    assert r.status_code == 400

def test_20_register_login_duplicate_and_invalid_creds():
    u = f"user_{uuid.uuid4().hex[:8]}"
    p = "Passw0rd!"

    r = post_json("/api/register", {"username": u, "password": p})
    assert r.status_code in (201, 400)

    r2 = post_json("/api/register", {"username": u, "password": p})
    assert r2.status_code == 400

    r3 = post_json("/api/login", {"username": u, "password": p})
    assert r3.status_code == 200
    assert "access_token" in r3.json()

    r4 = post_json("/api/login", {"username": u, "password": "bad"})
    assert r4.status_code == 401

def test_30_api_key_and_chat_auth_flows():
    u = f"user_{uuid.uuid4().hex[:8]}"
    p = "Passw0rd!"
    post_json("/api/register", {"username": u, "password": p})

    r = post_json("/api/login", {"username": u, "password": p})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r0 = get("/api/chat")
    assert r0.status_code == 401

    r1 = post_json("/api/api-key", {}, headers=auth(token))
    assert r1.status_code == 201
    api_key = r1.json()["api_key"]
    assert api_key and isinstance(api_key, str)

    r2 = get("/api/chat", headers={"X-API-KEY": api_key})
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)

    # 415 si NO mandas content-type JSON
    s = session()
    r3 = s.post(f"{BASE_URL}/api/chat", data="{}", headers={"X-API-KEY": api_key}, timeout=TIMEOUT)
    assert r3.status_code == 415

    # Este test solo pasará si en tu app aceptas mimetype application/json aunque venga con charset
    r4 = s.post(
        f"{BASE_URL}/api/chat",
        data='{"content":"hola"}',
        headers={"X-API-KEY": api_key, "Content-Type": "application/json; charset=utf-8"},
        timeout=TIMEOUT,
    )
    assert r4.status_code == 201

    r5 = post_json("/api/chat", {"content": "   "}, headers={"X-API-KEY": api_key})
    assert r5.status_code == 400

def test_40_admin_edit_delete_and_permissions():
    ra = post_json("/api/login", {"username": "admin", "password": "admin"})
    assert ra.status_code == 200
    admin_token = ra.json()["access_token"]

    u = f"user_{uuid.uuid4().hex[:8]}"
    p = "Passw0rd!"
    post_json("/api/register", {"username": u, "password": p})
    ru = post_json("/api/login", {"username": u, "password": p})
    assert ru.status_code == 200
    user_token = ru.json()["access_token"]

    rpost = post_json("/api/chat", {"content": "mensaje para editar"}, headers=auth(user_token))
    assert rpost.status_code == 201

    rlist = get("/api/chat", headers=auth(admin_token))
    assert rlist.status_code == 200
    msgs = rlist.json()
    assert msgs
    msg_id = max(m["id"] for m in msgs)

    rforbidden = put_json(f"/api/chat/{msg_id}", {"content": "edit"}, headers=auth(user_token))
    assert rforbidden.status_code == 403

    rok = put_json(f"/api/chat/{msg_id}", {"content": "editado por admin"}, headers=auth(admin_token))
    assert rok.status_code == 200

    rdel = delete(f"/api/chat/{msg_id}", headers=auth(admin_token))
    assert rdel.status_code == 200

    rdel2 = delete("/api/chat/99999999", headers=auth(admin_token))
    assert rdel2.status_code == 404