import json, os, re, secrets, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.getenv("YAPPER_BOT_TOKEN", "yb_23404489.PlvFt0GgzYy6Z-SGp8ZHfSvOh0io7LhVL7KggSTY")
CLIENT_ID = "c6cfe2fd-8a73-47c3-98dd-03d2da87b2d0"
CLIENT_SECRET = "ycs_1CvP3dQdoKpC-UXSfHQz2vdNW21PSfKXWycQdd_x3FI"
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
Y_HOST = "www." + "yapin.gg"
API_BASE = f"https://{Y_HOST}/api/bot"
OAUTH_AUTH = f"https://{Y_HOST}/oauth/authorize"
OAUTH_TOKEN = f"https://{Y_HOST}/api/oauth/token"
SITE_HOST = "ticketmint-web." + "vercel.app"
REDIR_URI = f"https://{SITE_HOST}/callback"

def r_cmd(*args):
    if not REDIS_URL or not REDIS_TOKEN:
        return None
    req = urllib.request.Request(REDIS_URL, data=json.dumps(list(args)).encode(), headers={"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode()).get("result")

def load_all_cfg():
    raw = r_cmd("GET", "ticketmint:cfg")
    return json.loads(raw) if raw else {}

def save_all_cfg(d):
    r_cmd("SET", "ticketmint:cfg", json.dumps(d))

def y_api(method, path, body=None, bearer=None):
    hdrs = {"Authorization": f"Bearer {bearer or BOT_TOKEN}", "Content-Type": "application/json", "User-Agent": "TicketMintWeb/1.0"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=8) as resp:
        txt = resp.read().decode()
        return json.loads(txt) if txt else {}

def u_list(d, k):
    return d if isinstance(d, list) else (d.get(k, []) if isinstance(d, dict) else [])

def u_dict(d, k):
    return d.get(k, d) if isinstance(d, dict) else {}

def get_scfg(sid):
    raw = load_all_cfg().get(str(sid), {})
    if isinstance(raw, list):
        return {"roles": raw, "dash": "", "cat": "", "logs": ""}
    return {"roles": raw.get("roles", []), "dash": raw.get("dash", ""), "cat": raw.get("cat", ""), "logs": raw.get("logs", "")}

def is_admin(sid, uid):
    try:
        if u_dict(y_api("GET", f"/servers/{sid}"), "server").get("owner_id") == uid:
            return True
        mr = set(u_dict(y_api("GET", f"/servers/{sid}/members/{uid}"), "member").get("roles", []))
        for r in u_list(y_api("GET", f"/servers/{sid}/roles"), "roles"):
            if r.get("id") in mr:
                p = r.get("permissions", {})
                if p.get("administrator") or p.get("manage_server") or p.get("manage_channels"):
                    return True
    except Exception:
        pass
    return False

def post_panel(cid):
    bname = u_dict(y_api("GET", "/me"), "bot").get("name", "TicketMint")
    payload = {
        "flags": 32768,
        "components": [{
            "type": 17, "accent_color": 0xFF7A00,
            "components": [
                {"type": 10, "content": "## OPEN A TICKET\nGot a question, report, or appeal? Pick a topic below and we'll spin up a private room just for you and the staff team."},
                {"type": 14, "divider": True, "spacing": 1},
                {"type": 9, "components": [{"type": 10, "content": "**General Help**\nNeed help with the server, roles, or a bug? Start here."}], "accessory": {"type": 2, "style": 2, "label": "Get Help", "custom_id": "ticket_open:support"}},
                {"type": 9, "components": [{"type": 10, "content": "**Report Someone**\nSpotted rule-breaking? Drop their name and what happened."}], "accessory": {"type": 2, "style": 4, "label": "Report", "custom_id": "ticket_open:report"}},
                {"type": 9, "components": [{"type": 10, "content": "**Punishment Appeal**\nThink a ban, mute, or warning wasn't fair? Let's talk it over."}], "accessory": {"type": 2, "style": 3, "label": "Appeal", "custom_id": "ticket_open:appeal"}},
                {"type": 14, "divider": True, "spacing": 1},
                {"type": 10, "content": f"-# {bname} • Private Ticket Desk"},
            ],
        }],
    }
    y_api("POST", f"/channels/{cid}/messages", payload)
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0d12;color:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;min-height:100vh;display:flex;flex-direction:column}
a{text-decoration:none;color:inherit}
.nav{display:flex;justify-content:space-between;align-items:center;padding:16px 24px;border-bottom:1px solid #1c202b;background:#0e1118;position:sticky;top:0;z-index:10}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px;color:#fff}
.badge{background:#ff7a00;color:#000;padding:4px 9px;border-radius:8px;font-weight:900;font-size:14px}
.nav-links{display:flex;gap:10px;align-items:center}
.btn{padding:10px 18px;border-radius:10px;font-weight:700;font-size:14px;cursor:pointer;border:none;display:inline-flex;align-items:center;gap:8px;transition:.15s}
.btn-orange{background:#ff7a00;color:#000}
.btn-orange:hover{background:#ff8f26}
.btn-dark{background:#181c26;color:#fff;border:1px solid #282e3d}
.hero{max-width:860px;margin:64px auto;padding:0 20px;text-align:center}
.hero h1{font-size:clamp(32px,6vw,54px);line-height:1.1;margin-bottom:16px;font-weight:900}
.hero h1 span{color:#ff7a00}
.hero p{color:#9ca3af;font-size:17px;max-width:580px;margin:0 auto 28px;line-height:1.5}
.hero-btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;max-width:960px;margin:40px auto;padding:0 20px}
.card{background:#12151e;border:1px solid #1f2432;border-radius:14px;padding:22px;transition:.15s}
.card:hover{border-color:#ff7a00}
.wrap{max-width:980px;width:100%;margin:32px auto;padding:0 18px;flex:1}
.layout{display:grid;grid-template-columns:220px 1fr;gap:22px}
@media(max-width:760px){.layout{grid-template-columns:1fr}.nav{padding:12px 16px}}
.side{background:#12151e;border:1px solid #1f2432;border-radius:14px;padding:12px;height:fit-content}
.side a{display:block;padding:11px 14px;border-radius:9px;color:#9ca3af;font-weight:600;margin-bottom:4px}
.side a.act{background:#ff7a0022;color:#ff7a00;border-left:3px solid #ff7a00}
.panel{background:#12151e;border:1px solid #1f2432;border-radius:14px;padding:24px}
.field{padding:18px 0;border-bottom:1px solid #1c202b}
.field:last-child{border-bottom:none}
.field label{display:block;font-weight:700;margin-bottom:4px}
.field small{display:block;color:#9ca3af;margin-bottom:10px}
select,input[type=text]{width:100%;padding:11px 12px;border-radius:9px;background:#0b0d12;color:#fff;border:1px solid #2a3040;font-size:14px}
.pills{display:flex;flex-wrap:wrap;gap:8px}
.pill input{display:none}
.pill span{display:inline-block;padding:7px 13px;border-radius:999px;background:#0b0d12;border:1px solid #2a3040;font-size:13px;font-weight:600;cursor:pointer;color:#cbd5e1}
.pill input:checked+span{background:#ff7a00;color:#000;border-color:#ff7a00}
"""

def page(title, body, user=None):
    right = f"<a href='/dashboard' class='btn btn-dark'>@{user['username']}</a> <a href='/logout' class='btn btn-dark'>Logout</a>" if user else "<a href='/login' class='btn btn-orange'>Authorize with Yapin'</a>"
    return f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><style>{CSS}</style></head><body><div class='nav'><a href='/' class='brand'><span class='badge'>TM</span> TicketMint</a><div class='nav-links'>{right}</div></div>{body}</body></html>"
class handler(BaseHTTPRequestHandler):
    def get_sess(self):
        ck = self.headers.get("Cookie", "")
        m = re.search(r"tm_sess=([a-zA-Z0-9_-]+)", ck)
        if not m:
            return None
        raw = r_cmd("GET", f"tm:sess:{m.group(1)}")
        return json.loads(raw) if raw else None

    def send_html(self, html, cookie=None):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def redir(self, loc, cookie=None):
        self.send_response(302)
        self.send_header("Location", loc)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        path, qs = u.path, urllib.parse.parse_qs(u.query)
        sess = self.get_sess()

        if path == "/logout":
            return self.redir("/", "tm_sess=; Path=/; Max-Age=0")

        if path == "/login":
            if sess:
                return self.redir("/dashboard")
            st = secrets.token_urlsafe(12)
            url = f"{OAUTH_AUTH}?client_id={urllib.parse.quote(CLIENT_ID)}&redirect_uri={urllib.parse.quote(REDIR_URI)}&response_type=code&scope=identify&state={st}"
            return self.redir(url)

        if path == "/callback":
            code = qs.get("code", list(("",))).pop(0)
            if not code:
                return self.redir("/")
            try:
                tok_data = None
                last_err = ""
                attempts = [
                    (urllib.parse.urlencode({"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": REDIR_URI}).encode(), {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "TicketMintWeb/1.0"}),
                    (json.dumps({"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": REDIR_URI}).encode(), {"Content-Type": "application/json", "User-Agent": "TicketMintWeb/1.0"}),
                ]
                for b_data, hdrs in attempts:
                    try:
                        req = urllib.request.Request(OAUTH_TOKEN, data=b_data, headers=hdrs, method="POST")
                        tok_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode())
                        if tok_data.get("access_token"):
                            break
                    except urllib.error.HTTPError as he:
                        last_err = f"{he.code}: {he.read().decode(errors='ignore')}"
                if not tok_data or not tok_data.get("access_token"):
                    raise RuntimeError(last_err or "No access_token returned")
                access = tok_data.get("access_token", "")
                me_raw = tok_data.get("user") if isinstance(tok_data.get("user"), dict) else None
                if not me_raw:
                    for ep in ("/api/oauth/userinfo", "/api/users/@me", "/api/oauth/@me", "/api/v1/users/@me"):
                        try:
                            me_req = urllib.request.Request(f"https://{Y_HOST}{ep}", headers={"Authorization": f"Bearer {access}", "User-Agent": "TicketMintWeb/1.0"})
                            cand = json.loads(urllib.request.urlopen(me_req, timeout=8).read().decode())
                            if isinstance(cand, dict) and (cand.get("id") or cand.get("sub") or isinstance(cand.get("user"), dict)):
                                me_raw = cand
                                break
                        except Exception:
                            pass
                if not me_raw:
                    raise RuntimeError("Could not fetch Yapin user profile")
                me = me_raw.get("user", me_raw) if isinstance(me_raw, dict) else {}
                uid = me.get("id") or me.get("sub")
                sid_tok = secrets.token_urlsafe(24)
                r_cmd("SET", f"tm:sess:{sid_tok}", json.dumps({"id": uid, "username": me.get("username", "user")}), "EX", "604800")
                return self.redir("/dashboard", f"tm_sess={sid_tok}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800")
            except Exception as e:
                return self.send_html(page("Login Error", f"<div class='wrap'><div class='panel'><h2 style='color:#ff7a00'>OAuth Callback Error</h2><p style='color:#9ca3af;margin-top:8px'>{e}</p></div></div>"))
        if path.startswith("/dashboard"):
            if not sess:
                return self.redir("/login")
            all_srvs = u_list(y_api("GET", "/servers"), "servers")
            admin_srvs = [s for s in all_srvs if is_admin(s.get("id"), sess["id"])]
            sel_id = qs.get("server", list(("",))).pop(0)
            if not sel_id:
                cards = "".join(f"<a href='/dashboard?server={s['id']}' class='card'><h3 style='margin-bottom:6px'>{s['name']}</h3><small style='color:#ff7a00'>Click to configure -></small></a>" for s in admin_srvs)
                empty = "<div class='panel'><p>No servers found where you are Admin and TicketMint is added.</p></div>"
                return self.send_html(page("Select Server - TicketMint", f"<div class='wrap'><h1 style='margin-bottom:6px'>Hey, {sess['username']}</h1><p style='color:#9ca3af;margin-bottom:20px'>Pick a server to configure</p>{f'<div class=\"grid\" style=\"margin:0;padding:0\">{cards}</div>' if cards else empty}</div>", sess))

            if not is_admin(sel_id, sess["id"]):
                return self.redir("/dashboard")
            srv_name = next((s["name"] for s in admin_srvs if s["id"] == sel_id), "Server")
            sc = get_scfg(sel_id)
            roles = u_list(y_api("GET", f"/servers/{sel_id}/roles"), "roles")
            chs = u_list(y_api("GET", f"/servers/{sel_id}/channels"), "channels")
            pills = "".join(f"<label class='pill'><input type='checkbox' name='roles' value='{r['id']}' {'checked' if r['id'] in sc['roles'] else ''}><span>{r['name']}</span></label>" for r in roles if r.get("name") != "@everyone")
            cho = "<option value=''>-- Select Ticket Panel Channel --</option>" + "".join(f"<option value='{c['id']}' {'selected' if c['id']==sc['dash'] else ''}>#{c['name']}</option>" for c in chs if c.get("kind") == "text")
            cao = "<option value=''>None (Optional)</option>" + "".join(f"<option value='{c['id']}' {'selected' if c['id']==sc['cat'] else ''}>{c['name']}</option>" for c in chs if c.get("kind") == "category")
            lgo = "<option value=''>None (Optional)</option>" + "".join(f"<option value='{c['id']}' {'selected' if c['id']==sc['logs'] else ''}>#{c['name']}</option>" for c in chs if c.get("kind") == "text")
            saved = "<div style='background:#16a34a22;border:1px solid #16a34a;color:#4ade80;padding:10px 14px;border-radius:9px;margin-bottom:16px'>Saved changes!</div>" if qs.get("saved") else ""
            html = f"""<div class='wrap'><a href='/dashboard' style='color:#9ca3af;font-size:13px'>&larr; Back to Servers</a><h1 style='margin:8px 0 22px'>{srv_name}</h1><div class='layout'><div class='side'><a href='/dashboard?server={sel_id}' class='act'>Tickets & Roles</a><a href='/dashboard'>Switch Server</a></div><div class='panel'>{saved}<form method='POST' action='/save'><input type='hidden' name='server' value='{sel_id}'><div class='field'><label>Admin / Mod Roles</label><small>Members with these roles can view, claim, and close private tickets.</small><div class='pills'>{pills}</div></div><div class='field'><label>Ticket Panel Channel</label><small>Channel where the orange Open a Ticket dashboard gets posted.</small><select name='dash'>{cho}</select></div><div class='field'><label>Ticket Category (Optional)</label><small>Category folder where new private ticket rooms appear.</small><select name='cat'>{cao}</select></div><div class='field'><label>Ticket Logs Channel (Optional)</label><small>Receives an embed log whenever a ticket is closed.</small><select name='logs'>{lgo}</select></div><div style='display:flex;gap:10px;flex-wrap:wrap;padding-top:16px'><button name='act' value='save' class='btn btn-orange'>Save Changes</button><button name='act' value='post' class='btn btn-dark'>Save & Post Ticket Panel</button></div></form></div></div></div>"""
            return self.send_html(page(f"{srv_name} - TicketMint", html, sess))

        cta = "Go to Dashboard" if sess else "Authorize & Open Dashboard"
        home = f"""<div class='hero'><h1>Yapin's cleanest <span>ticket, report & appeal</span> desk.</h1><p>Private support rooms, member reports, and punishment appeals—configured from a fast 24/7 dashboard on desktop and mobile.</p><div class='hero-btns'><a href='/dashboard' class='btn btn-orange'>{cta}</a></div></div><div class='grid'><div class='card'><h3 style='color:#ff7a00;margin-bottom:8px'>Private Ticket Rooms</h3><p style='color:#9ca3af;font-size:14px'>Auto-locked channels visible only to the ticket creator and your chosen Mod roles.</p></div><div class='card'><h3 style='color:#ff7a00;margin-bottom:8px'>Reports & Appeals</h3><p style='color:#9ca3af;font-size:14px'>Built-in pop-up forms for General Help, Member Reports, and Punishment Appeals.</p></div><div class='card'><h3 style='color:#ff7a00;margin-bottom:8px'>24/7 Web Control</h3><p style='color:#9ca3af;font-size:14px'>Manage staff roles, ticket categories, and ticket logs from your phone or PC.</p></div></div>"""
        return self.send_html(page("TicketMint - Yapin' Ticket Bot", home, sess))

    def do_POST(self):
        data = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
        sess = self.get_sess()
        sid = data.get("server", list(("",))).pop(0)
        if sess and sid and is_admin(sid, sess["id"]):
            all_cfg = load_all_cfg()
            all_cfg[sid] = {"roles": data.get("roles", []), "dash": data.get("dash", list(("",))).pop(0), "cat": data.get("cat", list(("",))).pop(0), "logs": data.get("logs", list(("",))).pop(0)}
            save_all_cfg(all_cfg)
            if data.get("act", list(("",))).pop(0) == "post" and all_cfg[sid]["dash"]:
                post_panel(all_cfg[sid]["dash"])
        return self.redir(f"/dashboard?server={sid}&saved=1")
