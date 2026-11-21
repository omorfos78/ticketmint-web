{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.py" }
  ]
}
import base64
import html
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.getenv("YAPPER_BOT_TOKEN", "yb_23404489.PlvFt0GgzYy6Z-SGp8ZHfSvOh0io7LhVL7KggSTY")
CLIENT_ID = "c6cfe2fd-8a73-47c3-98dd-03d2da87b2d0"
CLIENT_SECRET = "ycs_1CvP3dQdoKpC-UXSfHQz2vdNW21PSfKXWycQdd_x3FI"
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL", "https://profound-seasnail-108379.upstash.io").rstrip("/")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "gQAAAAAAAadbAAIgcDI4MTE2MjY4ODFkZGM0ZmQ1Yjg0NGE5MmU5YTAwYTI3Nw")
Y_HOST = "www." + "yapin.gg"
API_BASE = f"https://{Y_HOST}/api/bot"
OAUTH_AUTH = f"https://{Y_HOST}/oauth/authorize"
OAUTH_TOKEN = f"https://{Y_HOST}/api/oauth/token"
SITE_HOST = "ticketmint-web." + "vercel.app"
REDIR_URI = f"https://{SITE_HOST}/callback"
INVITE_URL = "https://" + "yapin.gg/bot/23404489-32ad-42d7-ac93-c1ba71cb2574"

ALL_COMMANDS = [
    ("ticketpanel", "/ticketpanel", "Post the orange Open a Ticket panel"),
    ("claimticket", "/claimticket", "Claim an open ticket room"),
    ("ticketclose", "/ticketclose", "Close and log an active ticket"),
    ("modroles", "/modroles", "Add, remove, or view staff roles"),
    ("setwelcomechannel", "/setwelcomechannel", "Set the automatic welcome channel"),
    ("announce", "/announce", "Post styled announcements in chat"),
    ("pfp", "/pfp", "View any member's full-size profile picture"),
    ("makeitquote", "/makeitquote", "Generate a quote card PNG from text"),
    ("replyquote", "@TicketMint Reply Quote", "Reply to a message and ping @TicketMint to quote it"),
]


def esc(val):
    return html.escape(str(val or ""), quote=True)


def r_cmd(*args):
    if not REDIS_URL or not REDIS_TOKEN:
        return None
    req = urllib.request.Request(
        REDIS_URL,
        data=json.dumps(list(args)).encode("utf-8"),
        headers={"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8")).get("result")


def load_all_cfg():
    try:
        raw = r_cmd("GET", "ticketmint:cfg")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def save_all_cfg(d):
    try:
        r_cmd("SET", "ticketmint:cfg", json.dumps(d))
    except Exception:
        pass


def y_api(method, path, body=None, bearer=None):
    hdrs = {
        "Authorization": f"Bearer {bearer or BOT_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "TicketMintWeb/1.0",
    }
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=8) as resp:
        txt = resp.read().decode("utf-8")
        return json.loads(txt) if txt else {}


def safe_y(method, path, body=None):
    try:
        return y_api(method, path, body)
    except Exception:
        return {}


def u_list(d, k):
    return d if isinstance(d, list) else (d.get(k, []) if isinstance(d, dict) else [])


def u_dict(d, k):
    return d.get(k, d) if isinstance(d, dict) else {}


def get_scfg(sid):
    raw = load_all_cfg().get(str(sid), {})
    if isinstance(raw, list):
        raw = {"roles": raw}
    return {
        "roles": raw.get("roles", []),
        "dash": raw.get("dash", ""),
        "cat": raw.get("cat", ""),
        "logs": raw.get("logs", ""),
        "welcome": raw.get("welcome", ""),
        "w_title": raw.get("w_title", "Welcome!"),
        "w_msg": raw.get("w_msg", "Welcome {user} to {server}!"),
        "w_banner": raw.get("w_banner", ""),
        "w_color": raw.get("w_color", "#ff7a00"),
        "goodbye": raw.get("goodbye", ""),
        "g_msg": raw.get("g_msg", "{user} just left {server}."),
        "disabled_cmds": raw.get("disabled_cmds", []),
    }


def is_admin(sid, uid):
    try:
        srv = u_dict(safe_y("GET", f"/servers/{sid}"), "server")
        if str(srv.get("owner_id", "")) == str(uid):
            return True
        mem = u_dict(safe_y("GET", f"/servers/{sid}/members/{uid}"), "member")
        mr = set(mem.get("roles", []))
        for r in u_list(safe_y("GET", f"/servers/{sid}/roles"), "roles"):
            if r.get("id") in mr:
                p = r.get("permissions", {})
                if isinstance(p, dict) and (p.get("administrator") or p.get("manage_server") or p.get("manage_channels")):
                    return True
    except Exception:
        pass
    return False


def post_panel(cid):
    bname = u_dict(safe_y("GET", "/me"), "bot").get("name", "TicketMint")
    payload = {
        "flags": 32768,
        "components": [{
            "type": 17,
            "accent_color": 0xFF7A00,
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
    safe_y("POST", f"/channels/{cid}/messages", payload)


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0d12;color:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;min-height:100vh;display:flex;flex-direction:column}
a{text-decoration:none;color:inherit}
.nav{display:flex;justify-content:space-between;align-items:center;padding:16px 24px;border-bottom:1px solid #1c202b;background:#0e1118;position:sticky;top:0;z-index:10}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px;color:#fff}
.badge{background:#ff7a00;color:#000;padding:4px 9px;border-radius:8px;font-weight:900;font-size:14px}
.nav-links{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.btn{padding:10px 18px;border-radius:10px;font-weight:700;font-size:14px;cursor:pointer;border:none;display:inline-flex;align-items:center;gap:8px;transition:.15s}
.btn-orange{background:#ff7a00;color:#000}
.btn-orange:hover{background:#ff8f26}
.btn-dark{background:#181c26;color:#fff;border:1px solid #282e3d}
.btn-dark:hover{border-color:#ff7a00}
.hero{max-width:860px;margin:64px auto;padding:0 20px;text-align:center}
.hero h1{font-size:clamp(32px,6vw,54px);line-height:1.1;margin-bottom:16px;font-weight:900}
.hero h1 span{color:#ff7a00}
.hero p{color:#9ca3af;font-size:17px;max-width:580px;margin:0 auto 28px;line-height:1.5}
.hero-btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;max-width:960px;margin:40px auto;padding:0 20px}
.card{background:#12151e;border:1px solid #1f2432;border-radius:14px;padding:22px;transition:.15s}
.card:hover{border-color:#ff7a00}
.srv-row{display:flex;align-items:center;justify-content:space-between;background:#12151e;border:1px solid #1f2432;border-radius:14px;padding:18px 22px;margin-bottom:12px;transition:.15s}
.srv-row:hover{border-color:#ff7a00;background:#161a26}
.srv-left{display:flex;align-items:center;gap:16px}
.srv-ico{width:46px;height:46px;border-radius:12px;background:#1b2030;border:1px solid #2a3147;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px;color:#fff;overflow:hidden;flex-shrink:0}
.srv-ico img{width:100%;height:100%;object-fit:cover}
.wrap{max-width:980px;width:100%;margin:32px auto;padding:0 18px;flex:1}
.layout{display:grid;grid-template-columns:220px 1fr;gap:22px}
@media(max-width:760px){.layout{grid-template-columns:1fr}.nav{padding:12px 16px}}
.side{background:#12151e;border:1px solid #1f2432;border-radius:14px;padding:12px;height:fit-content}
.side a{display:block;padding:11px 14px;border-radius:9px;color:#9ca3af;font-weight:600;margin-bottom:4px;font-size:14px}
.side a:hover{color:#fff;background:#181c28}
.side a.act{background:#ff7a0022;color:#ff7a00;border-left:3px solid #ff7a00}
.side hr{border:none;border-top:1px solid #1c202b;margin:8px 0}
.panel{background:#12151e;border:1px solid #1f2432;border-radius:14px;padding:24px}
.field{padding:18px 0;border-bottom:1px solid #1c202b}
.field:last-child{border-bottom:none}
.field label{display:block;font-weight:700;margin-bottom:4px}
.field small{display:block;color:#9ca3af;margin-bottom:10px}
select,input[type=text],textarea{width:100%;padding:11px 12px;border-radius:9px;background:#0b0d12;color:#fff;border:1px solid #2a3040;font-size:14px;font-family:inherit}
textarea{min-height:110px;resize:vertical}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:600px){.row2{grid-template-columns:1fr}}
.pills{display:flex;flex-wrap:wrap;gap:8px}
.pill input{display:none}
.pill span{display:inline-block;padding:7px 13px;border-radius:999px;background:#0b0d12;border:1px solid #2a3040;font-size:13px;font-weight:600;cursor:pointer;color:#cbd5e1}
.pill input:checked+span{background:#ff7a00;color:#000;border-color:#ff7a00}
.cmd-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 14px;border-radius:10px;background:#0b0d12;border:1px solid #1f2432;margin-bottom:9px}
.chk-line{display:flex;align-items:center;gap:10px;cursor:pointer;font-weight:600;font-size:14px}
.chk-line input{width:17px;height:17px;accent-color:#ff7a00}
.preview-box{background:#0b0d12;border:1px solid #242a3a;border-left:4px solid #ff7a00;border-radius:10px;padding:14px 16px;margin-top:10px}
"""


def page(title, body, user=None):
    inv = f"<a href='{INVITE_URL}' class='btn btn-dark'>+ Invite Bot</a>"
    right = (
        f"{inv} <a href='/dashboard' class='btn btn-dark'>@{esc(user['username'])}</a> <a href='/logout' class='btn btn-dark'>Logout</a>"
        if user
        else f"{inv} <a href='/login' class='btn btn-orange'>Authorize with Yapin'</a>"
    )
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
        f"<div class='nav'><a href='/' class='brand'><span class='badge'>TM</span> TicketMint</a><div class='nav-links'>{right}</div></div>"
        f"{body}</body></html>"
    )


def decode_jwt(tok):
    try:
        parts = tok.split(".")
        if len(parts) < 2:
            return None
        p = parts.pop(1)
        p += "=" * (-len(p) % 4)
        obj = json.loads(base64.urlsafe_b64decode(p.encode("utf-8")).decode("utf-8"))
        return obj if isinstance(obj, dict) and (obj.get("id") or obj.get("sub") or obj.get("user_id")) else None
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):
    def get_sess(self):
        ck = self.headers.get("Cookie", "")
        m = re.search(r"tm_sess=([a-zA-Z0-9_-]+)", ck)
        if not m:
            return None
        try:
            raw = r_cmd("GET", f"tm:sess:{m.group(1)}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def send_html(self, html_body, cookie=None):
        data = html_body.encode("utf-8")
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
            url = (
                f"{OAUTH_AUTH}?client_id={urllib.parse.quote(CLIENT_ID)}"
                f"&redirect_uri={urllib.parse.quote(REDIR_URI)}"
                f"&response_type=code&scope=identify&state={st}"
            )
            return self.redir(url)

        if path == "/callback":
            code = qs.get("code", [""])[0]
            if not code:
                return self.redir("/")
            try:
                tok_data = None
                last_err = ""
                attempts = [
                    (
                        urllib.parse.urlencode({
                            "client_id": CLIENT_ID,
                            "client_secret": CLIENT_SECRET,
                            "grant_type": "authorization_code",
                            "code": code,
                            "redirect_uri": REDIR_URI,
                        }).encode("utf-8"),
                        {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "TicketMintWeb/1.0"},
                    ),
                    (
                        json.dumps({
                            "client_id": CLIENT_ID,
                            "client_secret": CLIENT_SECRET,
                            "grant_type": "authorization_code",
                            "code": code,
                            "redirect_uri": REDIR_URI,
                        }).encode("utf-8"),
                        {"Content-Type": "application/json", "User-Agent": "TicketMintWeb/1.0"},
                    ),
                ]
                for b_data, hdrs in attempts:
                    try:
                        req = urllib.request.Request(OAUTH_TOKEN, data=b_data, headers=hdrs, method="POST")
                        tok_data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode("utf-8"))
                        if tok_data.get("access_token"):
                            break
                    except urllib.error.HTTPError as he:
                        last_err = f"{he.code}: {he.read().decode(errors='ignore')}"
                if not tok_data or not tok_data.get("access_token"):
                    raise RuntimeError(last_err or "No access_token returned")
                access = tok_data.get("access_token", "")
                me_raw = tok_data.get("user") if isinstance(tok_data.get("user"), dict) else decode_jwt(tok_data.get("id_token", "") or access)
                if not me_raw:
                    for ep in ("/api/oauth/me", "/api/oauth/userinfo", "/api/me", "/api/user", "/api/users/me", "/api/users/@me", "/oauth/userinfo"):
                        try:
                            me_req = urllib.request.Request(
                                f"https://{Y_HOST}{ep}",
                                headers={"Authorization": f"Bearer {access}", "User-Agent": "TicketMintWeb/1.0"},
                            )
                            cand = json.loads(urllib.request.urlopen(me_req, timeout=8).read().decode("utf-8"))
                            if isinstance(cand, dict):
                                inner = cand.get("user", cand) if isinstance(cand.get("user"), dict) else cand
                                if inner.get("id") or inner.get("user_id") or inner.get("sub"):
                                    me_raw = inner
                                    break
                        except Exception:
                            pass
                if not me_raw:
                    raise RuntimeError("Could not fetch Yapin user profile")
                uid = me_raw.get("id") or me_raw.get("user_id") or me_raw.get("sub")
                uname = me_raw.get("username") or me_raw.get("preferred_username") or me_raw.get("name") or me_raw.get("display_name") or "user"
                sid_tok = secrets.token_urlsafe(24)
                r_cmd("SET", f"tm:sess:{sid_tok}", json.dumps({"id": uid, "username": uname}), "EX", "604800")
                return self.redir("/dashboard", f"tm_sess={sid_tok}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800")
            except Exception as e:
                return self.send_html(
                    page("Login Error", f"<div class='wrap'><div class='panel'><h2 style='color:#ff7a00'>OAuth Callback Error</h2><p style='color:#9ca3af;margin-top:8px'>{esc(e)}</p></div></div>")
                )

        if path.startswith("/dashboard"):
            if not sess:
                return self.redir("/login")
            all_srvs = []
            try:
                cached = r_cmd("GET", "ticketmint:servers")
                if cached:
                    all_srvs = json.loads(cached)
            except Exception:
                pass
            for sp in ("/servers", "/me"):
                res = safe_y("GET", sp)
                cand = u_list(res, "servers") or (res.get("bot", {}).get("servers", []) if isinstance(res, dict) and isinstance(res.get("bot"), dict) else [])
                for c in cand:
                    if c.get("id") and not any(str(x.get("id")) == str(c.get("id")) for x in all_srvs):
                        all_srvs.append(c)
            admin_srvs = [
                s for s in all_srvs
                if not s.get("owner_id")
                or str(s.get("owner_id")) == str(sess["id"])
                or s.get("owner") is True
                or is_admin(s.get("id"), sess["id"])
            ]
            sel_id = qs.get("server", [""])[0].strip()
            if not sel_id:
                rows = []
                for s in admin_srvs:
                    sname = s.get("name", "Server")
                    ico = f"<img src='{esc(s['icon'])}' alt=''>" if s.get("icon") else esc(sname[:1].upper())
                    mc = f"{s['member_count']} members" if s.get("member_count") else "Ready to configure"
                    rows.append(
                        f"<a href='/dashboard?server={esc(s['id'])}' class='srv-row'>"
                        f"<div class='srv-left'><div class='srv-ico'>{ico}</div><div>"
                        f"<h3 style='font-size:17px;margin-bottom:3px'>{esc(sname)}</h3>"
                        f"<small style='color:#9ca3af'>{esc(mc)}</small></div></div>"
                        f"<span style='color:#ff7a00;font-weight:700;font-size:14px'>Configure &rarr;</span></a>"
                    )
                cards = "".join(rows)
                add_box = (
                    f"<div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><a href='{INVITE_URL}' class='btn btn-orange'>+ Invite TicketMint to Server</a></div>"
                    f"<form method='GET' action='/dashboard' style='display:flex;gap:10px;max-width:440px;margin-top:16px'>"
                    f"<input type='text' name='server' placeholder='Or paste Server ID directly...' required>"
                    f"<button class='btn btn-dark' type='submit'>Open</button></form>"
                )
                empty = f"<div class='panel'><p style='margin-bottom:8px'>Add <b>TicketMint</b> to your server to configure it here.</p>{add_box}</div>"
                footer_inv = f"<div style='text-align:center;margin-top:20px'><a href='{INVITE_URL}' class='btn btn-dark'>+ Invite TicketMint to Another Server</a></div>" if cards else ""
                return self.send_html(
                    page("Select Server - TicketMint", f"<div class='wrap' style='max-width:760px'><div style='text-align:center;margin:20px 0 32px'><h1 style='font-size:34px;margin-bottom:6px'>Hey, {esc(sess['username'])}</h1><p style='color:#9ca3af'>Pick a server to configure.</p></div>{cards if cards else empty}{footer_inv}</div>", sess)
                )

            srv_obj = next((s for s in admin_srvs if str(s.get("id")) == str(sel_id)), None)
            fetched = u_dict(safe_y("GET", f"/servers/{sel_id}"), "server")
            if not srv_obj:
                if fetched and fetched.get("id") and not is_admin(sel_id, sess["id"]):
                    return self.redir("/dashboard")
                srv_obj = fetched if fetched and fetched.get("id") else {"id": sel_id, "name": f"Server ({sel_id})"}
            srv_name = (fetched.get("name") if isinstance(fetched, dict) else None) or srv_obj.get("name", f"Server ({sel_id})")
            sc = get_scfg(sel_id)
            tab = qs.get("tab", ["tickets"])[0].strip().lower()
            if tab not in ("tickets", "welcome", "announce", "commands"):
                tab = "tickets"

            meta = {}
            try:
                mraw = r_cmd("GET", f"ticketmint:meta:{sel_id}")
                if mraw:
                    meta = json.loads(mraw)
            except Exception:
                pass
            roles = u_list(safe_y("GET", f"/servers/{sel_id}/roles"), "roles") or meta.get("roles", [])
            chs = u_list(safe_y("GET", f"/servers/{sel_id}/channels"), "channels") or meta.get("channels", [])
            if roles or chs:
                try:
                    r_cmd("SET", f"ticketmint:meta:{sel_id}", json.dumps({"roles": roles, "channels": chs}))
                except Exception:
                    pass

            is_cat = lambda c: str(c.get("kind", "")).lower() in ("category", "folder", "group") or str(c.get("type", "")).lower() in ("category", "folder", "group", "4") or bool(c.get("is_category"))
            is_txt = lambda c: not is_cat(c) and str(c.get("kind", "text")).lower() not in ("voice", "stage") and str(c.get("type", "0")).lower() not in ("voice", "stage", "2", "13")
            txt_chs = [c for c in chs if is_txt(c)]
            cat_chs = [c for c in chs if is_cat(c)]

            def ch_opts(items, selected_id, empty_label, prefix="#"):
                out = [f"<option value=''>{esc(empty_label)}</option>"]
                for c in items:
                    cid = str(c.get("id", ""))
                    cname = c.get("name", "channel")
                    out.append(f"<option value='{esc(cid)}' {'selected' if cid == str(selected_id) else ''}>{esc(prefix)}{esc(cname)}</option>")
                return "".join(out)

            notice = ""
            if qs.get("saved"):
                notice = "<div style='background:#16a34a22;border:1px solid #16a34a;color:#4ade80;padding:10px 14px;border-radius:9px;margin-bottom:16px'>Saved changes! Your bot remembers these settings automatically.</div>"
            elif qs.get("sent"):
                notice = "<div style='background:#16a34a22;border:1px solid #16a34a;color:#4ade80;padding:10px 14px;border-radius:9px;margin-bottom:16px'>Announcement sent to your server!</div>"
            elif qs.get("err"):
                notice = f"<div style='background:#dc262622;border:1px solid #dc2626;color:#f87171;padding:10px 14px;border-radius:9px;margin-bottom:16px'>{esc(qs.get('err', ['Error'])[0])}</div>"

            if tab == "tickets":
                pills = "".join(
                    f"<label class='pill'><input type='checkbox' name='roles' value='{esc(r['id'])}' {'checked' if r['id'] in sc['roles'] else ''}><span>{esc(r.get('name', 'Role'))}</span></label>"
                    for r in roles if r.get("name") != "@everyone"
                )
                if not pills:
                    pills = "<span style='color:#9ca3af;font-size:13px'>Make sure <b>python bot.py</b> is running and TicketMint is in this server, then refresh.</span>"
                cho = ch_opts(txt_chs, sc["dash"], "-- Select Ticket Panel Channel --", "#")
                cao = ch_opts(cat_chs, sc["cat"], "None (Optional)", "")
                lgo = ch_opts(txt_chs, sc["logs"], "None (Optional)", "#")
                panel_html = (
                    f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='tickets'>"
                    f"<div class='field'><label>Admin / Mod Roles</label><small>Members with these roles can view, claim, and close private tickets.</small><div class='pills'>{pills}</div></div>"
                    f"<div class='field'><label>Ticket Panel Channel</label><small>Channel where the orange Open a Ticket dashboard gets posted.</small><select name='dash'>{cho}</select></div>"
                    f"<div class='field'><label>Ticket Category (Optional)</label><small>Category folder where new private ticket rooms appear.</small><select name='cat'>{cao}</select></div>"
                    f"<div class='field'><label>Ticket Logs Channel (Optional)</label><small>Receives an embed log whenever a ticket is closed.</small><select name='logs'>{lgo}</select></div>"
                    f"<div style='display:flex;gap:10px;flex-wrap:wrap;padding-top:16px'><button name='act' value='save' class='btn btn-orange'>Save Changes</button><button name='act' value='post' class='btn btn-dark'>Save &amp; Post Ticket Panel</button></div></form>"
                )
            elif tab == "welcome":
                w_cho = ch_opts(txt_chs, sc["welcome"], "Disabled (No Welcome Channel)", "#")
                g_cho = ch_opts(txt_chs, sc["goodbye"], "Disabled (No Goodbye Channel)", "#")
                prev_col = sc["w_color"] if str(sc["w_color"]).startswith("#") else "#ff7a00"
                prev_txt = esc(sc["w_msg"]).replace("{user}", f"@{esc(sess['username'])}").replace("{server}", esc(srv_name))
                banner_prev = f"<img src='{esc(sc['w_banner'])}' style='width:100%;max-height:150px;object-fit:cover;border-radius:8px;margin-top:10px' alt=''>" if sc["w_banner"] else ""
                panel_html = (
                    f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='welcome'>"
                    f"<div class='field'><label>Welcome Channel</label><small>Channel where automatic welcome cards are posted when members join.</small><select name='welcome'>{w_cho}</select></div>"
                    f"<div class='field row2'><div><label>Welcome Embed Title</label><small>Heading shown at the top of the welcome card.</small><input type='text' name='w_title' value='{esc(sc['w_title'])}' placeholder='Welcome!'></div>"
                    f"<div><label>Accent Color (Hex)</label><small>Default TicketMint orange is #ff7a00.</small><input type='text' name='w_color' value='{esc(sc['w_color'])}' placeholder='#ff7a00'></div></div>"
                    f"<div class='field'><label>Welcome Message</label><small>Supports <b>{{user}}</b> and <b>{{server}}</b>.</small><input type='text' name='w_msg' value='{esc(sc['w_msg'])}' placeholder='Welcome {{user}} to {{server}}!'></div>"
                    f"<div class='field'><label>Welcome Banner Image URL (Optional)</label><small>Direct image link displayed inside the welcome embed.</small><input type='text' name='w_banner' value='{esc(sc['w_banner'])}' placeholder='https://...'>"
                    f"<div class='preview-box' style='border-left-color:{esc(prev_col)}'><div style='font-size:11px;color:#9ca3af;margin-bottom:4px'>LIVE EMBED PREVIEW</div>"
                    f"<div style='font-weight:800;font-size:15px;margin-bottom:4px'>{esc(sc['w_title'] or 'Welcome!')}</div>"
                    f"<div style='color:#cbd5e1;font-size:14px'>{prev_txt}</div>{banner_prev}</div></div>"
                    f"<div class='field'><label>Goodbye Channel (Optional)</label><small>Channel where goodbye messages are posted when a member leaves.</small><select name='goodbye'>{g_cho}</select></div>"
                    f"<div class='field'><label>Goodbye Message</label><small>Supports <b>{{user}}</b> and <b>{{server}}</b>.</small><input type='text' name='g_msg' value='{esc(sc['g_msg'])}' placeholder='{{user}} just left {{server}}.'></div>"
                    f"<div style='display:flex;gap:10px;flex-wrap:wrap;padding-top:16px'><button name='act' value='save' class='btn btn-orange'>Save Welcome &amp; Goodbye</button></div></form>"
                )
            elif tab == "announce":
                ann_cho = ch_opts(txt_chs, sc["dash"], "-- Select Target Channel --", "#")
                panel_html = (
                    f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='announce'>"
                    f"<div class='field'><label>Target Channel</label><small>Choose where TicketMint should post this announcement embed.</small><select name='ann_channel' required>{ann_cho}</select></div>"
                    f"<div class='field'><label>Announcement Title</label><small>Displayed as a bold heading inside the orange embed.</small><input type='text' name='ann_title' placeholder='Server Update!' required></div>"
                    f"<div class='field'><label>Announcement Message</label><small>Write your announcement details below.</small><textarea name='ann_body' placeholder='Hey everyone! Here is what is new...' required></textarea></div>"
                    f"<div class='field'><label class='chk-line'><input type='checkbox' name='ann_everyone' value='1'><span>Ping @everyone above the announcement</span></label></div>"
                    f"<div style='display:flex;gap:10px;flex-wrap:wrap;padding-top:16px'><button name='act' value='announce' class='btn btn-orange'>Send Announcement</button></div></form>"
                )
            else:
                disabled = set(sc["disabled_cmds"])
                cmd_items = "".join(
                    f"<div class='cmd-row'><div><div style='font-weight:700;font-size:14px'>{esc(label)}</div>"
                    f"<div style='color:#9ca3af;font-size:12px;margin-top:2px'>{esc(desc)}</div></div>"
                    f"<label class='pill'><input type='checkbox' name='enabled_cmds' value='{esc(key)}' {'checked' if key not in disabled else ''}><span>Enabled</span></label></div>"
                    for key, label, desc in ALL_COMMANDS
                )
                panel_html = (
                    f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='commands'>"
                    f"<div class='field'><label>Commands &amp; Tools</label><small>Toggle which TicketMint commands and features are active in <b>{esc(srv_name)}</b>.</small>{cmd_items}</div>"
                    f"<div style='display:flex;gap:10px;flex-wrap:wrap;padding-top:16px'><button name='act' value='save' class='btn btn-orange'>Save Command Settings</button></div></form>"
                )

            side_links = (
                f"<a href='/dashboard?server={esc(sel_id)}&tab=tickets' class='{'act' if tab=='tickets' else ''}'>Tickets &amp; Roles</a>"
                f"<a href='/dashboard?server={esc(sel_id)}&tab=welcome' class='{'act' if tab=='welcome' else ''}'>Welcome &amp; Goodbye</a>"
                f"<a href='/dashboard?server={esc(sel_id)}&tab=announce' class='{'act' if tab=='announce' else ''}'>Announcements</a>"
                f"<a href='/dashboard?server={esc(sel_id)}&tab=commands' class='{'act' if tab=='commands' else ''}'>Commands &amp; Tools</a>"
                f"<hr><a href='/dashboard'>Switch Server</a>"
            )
            html_out = (
                f"<div class='wrap'><a href='/dashboard' style='color:#9ca3af;font-size:13px'>&larr; Back to Servers</a>"
                f"<h1 style='margin:8px 0 22px'>{esc(srv_name)}</h1><div class='layout'><div class='side'>{side_links}</div>"
                f"<div class='panel'>{notice}{panel_html}</div></div></div>"
            )
            return self.send_html(page(f"{srv_name} - TicketMint", html_out, sess))

        cta = "Go to Dashboard" if sess else "Authorize & Open Dashboard"
        home = (
            f"<div class='hero'><h1>Yapin's cleanest <span>ticket, report &amp; appeal</span> desk.</h1>"
            f"<p>Private support rooms, member reports, and punishment appeals—configured from a fast 24/7 dashboard on desktop and mobile.</p>"
            f"<div class='hero-btns'><a href='/dashboard' class='btn btn-orange'>{cta}</a><a href='{INVITE_URL}' class='btn btn-dark'>+ Invite Bot to Server</a></div></div>"
            f"<div class='grid'><div class='card'><h3 style='color:#ff7a00;margin-bottom:8px'>Private Ticket Rooms</h3><p style='color:#9ca3af;font-size:14px'>Auto-locked channels visible only to the ticket creator and your chosen Mod roles.</p></div>"
            f"<div class='card'><h3 style='color:#ff7a00;margin-bottom:8px'>Reports &amp; Appeals</h3><p style='color:#9ca3af;font-size:14px'>Built-in pop-up forms for General Help, Member Reports, and Punishment Appeals.</p></div>"
            f"<div class='card'><h3 style='color:#ff7a00;margin-bottom:8px'>24/7 Web Control</h3><p style='color:#9ca3af;font-size:14px'>Manage staff roles, welcome cards, announcements, and commands from your phone or PC.</p></div></div>"
        )
        return self.send_html(page("TicketMint - Yapin' Ticket Bot", home, sess))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length).decode("utf-8", errors="ignore")
        data = urllib.parse.parse_qs(raw_body)
        sess = self.get_sess()
        sid = data.get("server", [""])[0].strip()
        tab = data.get("tab", ["tickets"])[0].strip().lower()
        act = data.get("act", ["save"])[0].strip().lower()
        if sess and sid:
            all_cfg = load_all_cfg()
            cur = get_scfg(sid)
            if tab == "tickets":
                cur["roles"] = data.get("roles", [])
                cur["dash"] = data.get("dash", [""])[0].strip()
                cur["cat"] = data.get("cat", [""])[0].strip()
                cur["logs"] = data.get("logs", [""])[0].strip()
                all_cfg[sid] = cur
                save_all_cfg(all_cfg)
                if act == "post" and cur["dash"]:
                    post_panel(cur["dash"])
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&saved=1")
            if tab == "welcome":
                cur["welcome"] = data.get("welcome", [""])[0].strip()
                cur["w_title"] = data.get("w_title", ["Welcome!"])[0].strip() or "Welcome!"
                cur["w_msg"] = data.get("w_msg", ["Welcome {user} to {server}!"])[0].strip() or "Welcome {user} to {server}!"
                cur["w_banner"] = data.get("w_banner", [""])[0].strip()
                w_col = data.get("w_color", ["#ff7a00"])[0].strip()
                cur["w_color"] = w_col if re.match(r"^#[0-9a-fA-F]{6}$", w_col) else "#ff7a00"
                cur["goodbye"] = data.get("goodbye", [""])[0].strip()
                cur["g_msg"] = data.get("g_msg", ["{user} just left {server}."])[0].strip() or "{user} just left {server}."
                all_cfg[sid] = cur
                save_all_cfg(all_cfg)
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=welcome&saved=1")
            if tab == "announce":
                ann_cid = data.get("ann_channel", [""])[0].strip()
                ann_title = data.get("ann_title", ["Announcement"])[0].strip() or "Announcement"
                ann_body = data.get("ann_body", [""])[0].strip()
                ping = "@everyone" if data.get("ann_everyone") else ""
                if not ann_cid or not ann_body:
                    return self.redir(
                        f"/dashboard?server={urllib.parse.quote(sid)}&tab=announce&err={urllib.parse.quote('Choose a channel and enter a message.')}"
                    )
                safe_y(
                    "POST",
                    f"/channels/{ann_cid}/messages",
                    {
                        "content": ping,
                        "embeds": [{
                            "description": f"## {ann_title}\n\n{ann_body}",
                            "color": 0xFF7A00,
                            "footer": {"text": f"Announced by @{sess['username']} • TicketMint"},
                        }],
                    },
                )
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=announce&sent=1")
            if tab == "commands":
                enabled = set(data.get("enabled_cmds", []))
                cur["disabled_cmds"] = [k for k, _, _ in ALL_COMMANDS if k not in enabled]
                all_cfg[sid] = cur
                save_all_cfg(all_cfg)
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&saved=1")
        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&saved=1")
