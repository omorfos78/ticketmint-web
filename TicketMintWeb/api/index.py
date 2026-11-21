import base64
import html
import json
import os
import random
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.getenv("YAPPER_BOT_TOKEN", "yb_23404489.PlvFt0GgzYy6Z-SGp8ZHfSvOh0io7LhVL7KggSTY")
CLIENT_ID = (os.getenv("YAPPER_CLIENT_ID") or os.getenv("CLIENT_ID") or "c6cfe2fd-8a73-47c3-98dd-03d2da87b2d0").strip()
CLIENT_SECRET = (os.getenv("YAPPER_CLIENT_SECRET") or os.getenv("CLIENT_SECRET") or "ycs_1CvP3dQdoKpC-UXSfHQz2vdNW21PSfKXWycQdd_x3FI").strip()
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL", "https://profound-seasnail-108379.upstash.io").rstrip("/")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "gQAAAAAAAadbAAIgcDI4MTE2MjY4ODFkZGM0ZmQ1Yjg0NGE5MmU5YTAwYTI3Nw")
Y_HOST = "www." + "yapin.gg"
API_BASE = f"https://{Y_HOST}/api/bot"
OAUTH_AUTH = f"https://{Y_HOST}/oauth/authorize"
OAUTH_TOKEN = f"https://{Y_HOST}/api/oauth/token"
SITE_HOST = os.getenv("SITE_HOST", "ticketmint-web." + "vercel.app").strip()
REDIR_URI = f"https://{SITE_HOST}/callback"
INVITE_URL = "https://" + "yapin.gg/bot/23404489-32ad-42d7-ac93-c1ba71cb2574"

DEFAULT_OPEN_MSG = "🎫 **{user}** opened **{ticket}** — *Reason:* {reason}"
DEFAULT_CLOSE_MSG = "🔒 **{ticket}** was closed by **{user}** — *Reason:* {reason}"
DEFAULT_CLAIM_MSG = "🛡️ **{ticket}** is now claimed by **{user}** — *Reason:* {reason}"

# (key, display_label, description, mod_only)
ALL_COMMANDS = [
    ("roll", "/roll", "Roll a random number from 1 to 999 (or 1 to max)", False),
    ("ticketpanel", "/ticketpanel", "Post the orange Open a Ticket panel", True),
    ("claimticket", "/claimticket", "Claim an open ticket room", True),
    ("ticketclose", "/ticketclose", "Close and log an active ticket", True),
    ("modroles", "/modroles", "Add, remove, or view staff roles", True),
    ("setwelcomechannel", "/setwelcomechannel", "Set the automatic welcome channel", True),
    ("verifypanel", "/verifypanel", "Post a 1-click member verification panel", True),
    ("announce", "/announce", "Post styled announcements in chat", True),
    ("warn", "/warn", "Issue an official staff warning to a user", True),
    ("clear", "/clear", "Bulk delete recent messages in a channel", True),
    ("slowmode", "/slowmode", "Set channel slowmode timer", True),
    ("role", "/role", "Add or remove a role on a member", True),
    ("pingrole", "/pingrole", "Manage allowed or protected pingable roles", True),
    ("pfp", "/pfp", "View any member's full-size profile picture", False),
    ("makeitquote", "/makeitquote", "Generate a quote card PNG from text", False),
    ("replyquote", "@TicketMint Reply Quote", "Reply to a message and ping @TicketMint to quote it", False),
    ("afk", "/afk", "Set an AFK status with an optional reason", False),
    ("serverinfo", "/serverinfo", "View server details and protection stats", False),
    ("userinfo", "/userinfo", "View a member's ID, roles, and staff status", False),
    ("poll", "/poll", "Create a quick poll with choices", False),
]


def ordinal_num(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    if 11 <= (n % 100) <= 13:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def esc(val):
    return html.escape(str(val or ""), quote=True)


def clean_err(raw_text):
    txt = re.sub(r"<[^>]+>", " ", str(raw_text or ""))
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:140] if txt else "Request failed"


def format_ping_mention(raw_ping):
    val = str(raw_ping or "").strip()
    if not val:
        return ""
    low = val.lower()
    if low in ("everyone", "@everyone"):
        return "@everyone"
    if low in ("here", "@here"):
        return "@here"
    if val.startswith("<@&") and val.endswith(">"):
        return val
    rid = re.sub(r"[<@&>]", "", val).strip()
    if rid.isdigit():
        return f"<@&{rid}>"
    return val if val.startswith("@") else f"@{val}"


def r_cmd(*args):
    if not REDIS_URL or not REDIS_TOKEN:
        return None
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                REDIS_URL,
                data=json.dumps(list(args)).encode("utf-8"),
                headers={"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                return json.loads(resp.read().decode("utf-8")).get("result")
        except Exception:
            if attempt == 0:
                time.sleep(0.1)
            else:
                return None


def load_all_cfg():
    try:
        raw = r_cmd("GET", "ticketmint:cfg")
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def save_all_cfg(d, sid=None):
    if not isinstance(d, dict):
        return
    try:
        r_cmd("SET", "ticketmint:cfg", json.dumps(d))
        if sid and str(sid) in d:
            r_cmd("SET", f"ticketmint:cfg:{sid}", json.dumps(d[str(sid)]))
    except Exception:
        pass


def queue_outbox(job):
    try:
        payload = dict(job) if isinstance(job, dict) else {}
        payload["ts"] = int(time.time())
        r_cmd("RPUSH", "ticketmint:outbox", json.dumps(payload))
        return True
    except Exception:
        return False


def y_api(method, path, body=None, bearer=None, base_url=None):
    hdrs = {
        "Authorization": f"Bearer {bearer or BOT_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    data = json.dumps(body).encode("utf-8") if body is not None else None
    root = (base_url or API_BASE).rstrip("/")
    last_exc = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(f"{root}{path}", data=data, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=4) as resp:
                txt = resp.read().decode("utf-8")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as he:
            last_exc = he
            if he.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(0.15)
                continue
            raise
        except Exception as e:
            last_exc = e
            if attempt == 0:
                time.sleep(0.15)
                continue
            raise last_exc


def safe_y(method, path, body=None):
    try:
        return y_api(method, path, body)
    except Exception:
        return {}


def pick_name(obj, fallback=""):
    if not isinstance(obj, dict):
        return fallback
    for k in ("name", "title", "label", "category_name", "parent_name", "display_name"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def is_cat_item(c):
    k = str(c.get("kind", "")).lower()
    t = str(c.get("type", "")).lower()
    return k in ("category", "folder", "group") or t in ("category", "folder", "group", "4") or bool(c.get("is_category"))


def is_voice_item(c):
    k = str(c.get("kind", "")).lower()
    t = str(c.get("type", "")).lower()
    return k in ("voice", "stage") or t in ("voice", "stage", "2", "13")


def resolve_server_name(sid, fetched=None, base_srv=None, meta=None):
    if isinstance(fetched, dict):
        n = pick_name(fetched) or pick_name(fetched.get("server") if isinstance(fetched.get("server"), dict) else {})
        if n and not re.match(r"^Server\s*\(", n, re.I):
            return n
    if isinstance(base_srv, dict):
        n = pick_name(base_srv)
        if n and not re.match(r"^Server\s*\(", n, re.I):
            return n
    if isinstance(meta, dict):
        n = pick_name(meta.get("server") if isinstance(meta.get("server"), dict) else meta)
        if n and not re.match(r"^Server\s*\(", n, re.I):
            return n
    try:
        cached = r_cmd("GET", "ticketmint:servers")
        if cached:
            parsed = json.loads(cached)
            if isinstance(parsed, list):
                for s in parsed:
                    if isinstance(s, dict) and str(s.get("id")) == str(sid):
                        n = pick_name(s)
                        if n:
                            return n
    except Exception:
        pass
    try:
        mraw = r_cmd("GET", f"ticketmint:meta:{sid}")
        if mraw:
            pm = json.loads(mraw)
            if isinstance(pm, dict):
                n = pick_name(pm.get("server") if isinstance(pm.get("server"), dict) else pm)
                if n:
                    return n
    except Exception:
        pass
    srv_res = safe_y("GET", f"/servers/{sid}")
    if isinstance(srv_res, dict):
        inner = srv_res.get("server") if isinstance(srv_res.get("server"), dict) else srv_res
        n = pick_name(inner)
        if n:
            return n
    return f"Server ({sid})"


def sync_server_metadata(sid, existing_meta=None):
    meta = dict(existing_meta or {})
    roles = meta.get("roles", []) if isinstance(meta.get("roles"), list) else []
    chs = meta.get("channels", []) if isinstance(meta.get("channels"), list) else []
    extra_cats = list(meta.get("categories", [])) if isinstance(meta.get("categories"), list) else []

    srv_full = safe_y("GET", f"/servers/{sid}")
    fetched = srv_full.get("server", srv_full) if isinstance(srv_full, dict) else {}

    r_res = safe_y("GET", f"/servers/{sid}/roles")
    r_list = r_res if isinstance(r_res, list) else (r_res.get("roles", []) if isinstance(r_res, dict) else [])
    if r_list:
        roles = r_list

    c_res = safe_y("GET", f"/servers/{sid}/channels")
    c_list = c_res if isinstance(c_res, list) else (c_res.get("channels", []) if isinstance(c_res, dict) else [])
    if c_list:
        chs = c_list

    for src in (c_res, fetched, srv_full):
        if isinstance(src, dict):
            for key in ("categories", "folders", "groups"):
                if isinstance(src.get(key), list):
                    extra_cats.extend(src[key])

    cat_map = {}
    for ec in extra_cats:
        if isinstance(ec, dict) and ec.get("id"):
            cid = str(ec["id"])
            cname = pick_name(ec)
            if cname and not re.match(r"^Category \([0-9a-f]{6,}\)$", cname, re.I):
                cat_map[cid] = cname

    children_by_parent = {}
    for c in chs:
        if isinstance(c, dict):
            if is_cat_item(c) and c.get("id"):
                cid = str(c["id"])
                cname = pick_name(c)
                if cname and cid not in cat_map:
                    cat_map[cid] = cname
            pid = c.get("parent_id") or c.get("category_id") or c.get("parentId")
            if pid:
                pid_s = str(pid)
                children_by_parent.setdefault(pid_s, []).append(f"#{c.get('name', 'channel')}")
                pname = c.get("parent_name") or c.get("category_name") or c.get("parentName")
                if isinstance(pname, str) and pname.strip() and pid_s not in cat_map:
                    cat_map[pid_s] = pname.strip()

    for pid_s, child_names in children_by_parent.items():
        if pid_s not in cat_map:
            preview = ", ".join(child_names[:2])
            if len(child_names) > 2:
                preview += f" +{len(child_names) - 2}"
            cat_map[pid_s] = f"Category ({preview})"

    cat_chs = [{"id": cid, "name": cname} for cid, cname in cat_map.items()]
    srv_name = pick_name(fetched if isinstance(fetched, dict) else {}, pick_name(meta.get("server") if isinstance(meta.get("server"), dict) else {}, ""))
    new_meta = {
        "roles": roles,
        "channels": chs,
        "categories": cat_chs,
        "server": {"id": sid, **({"name": srv_name} if srv_name else {})},
    }
    if roles or chs or cat_chs or srv_name:
        r_cmd("SET", f"ticketmint:meta:{sid}", json.dumps(new_meta))
    return new_meta, fetched if isinstance(fetched, dict) else {}


def post_raw_message(cid, payload):
    base_dict = payload if isinstance(payload, dict) else {"content": str(payload)}
    embeds_list = base_dict.get("embeds") if isinstance(base_dict.get("embeds"), list) else []
    first_desc = embeds_list[0].get("description", "") if embeds_list and isinstance(embeds_list[0], dict) else ""
    plain_text = base_dict.get("content") or first_desc or "TicketMint"

    variants = [base_dict, {"content": plain_text}, {"text": plain_text}, {"message": plain_text}]
    endpoints = [
        (API_BASE, f"/channels/{cid}/messages"),
        (f"https://{Y_HOST}/api", f"/bot/channels/{cid}/messages"),
        (API_BASE, "/messages"),
        (f"https://{Y_HOST}/api", "/bot/messages"),
    ]
    last_err = ""
    for base, ep in endpoints:
        for body in variants:
            send_body = {**body, "channel_id": cid} if ep.endswith("/messages") and not ep.startswith("/channels/") else body
            try:
                y_api("POST", ep, body=send_body, base_url=base)
                return True, ""
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                last_err = f"HTTP {he.code}: {clean_err(err_body)}"
            except Exception as e:
                last_err = clean_err(e)
    return False, last_err or "Could not deliver message to channel."


def send_msg_smart(cid, content="", title="", description="", color_hex="#ff7a00", image_url="", footer="", kind="message", ping="", extra=None):
    if not cid:
        return False, "No channel selected."
    try:
        c_int = int(str(color_hex or "#ff7a00").lstrip("#"), 16)
    except Exception:
        c_int = 0xFF7A00

    ping_formatted = format_ping_mention(ping)
    header_parts = []
    if ping_formatted:
        header_parts.append(ping_formatted)
    if content and content.strip() and content.strip() != ping_formatted and content.strip() != str(ping or "").strip():
        header_parts.append(content.strip())
    top_content = " ".join(header_parts).strip()

    body_text = str(description or "").strip()
    if not top_content and not body_text:
        top_content = f"**{title}**" if title else "TicketMint"

    embed_obj = {"description": body_text or "", "color": c_int}
    if title:
        embed_obj["title"] = str(title).strip()
    if image_url:
        embed_obj["image"] = {"url": str(image_url).strip()}
    if footer:
        embed_obj["footer"] = {"text": str(footer).strip()}

    payload = {"embeds": [embed_obj]}
    if top_content:
        payload["content"] = top_content

    post_raw_message(cid, payload)
    job = {
        "type": kind,
        "channel_id": str(cid),
        "ping": ping_formatted,
        "content": top_content,
        "text": top_content or body_text,
        "title": str(title or "").strip(),
        "description": body_text,
        "image_url": str(image_url or "").strip(),
        "footer": str(footer or "").strip(),
        "color": f"#{str(color_hex or '#ff7a00').lstrip('#')}",
    }
    if isinstance(extra, dict):
        job.update(extra)
    queued = queue_outbox(job)
    return True, ("" if queued else "Outbox queue unavailable")


def format_ticket_log_message(template, user_label, ticket_label, reason="", server_name="", claimer=""):
    txt = str(template or DEFAULT_OPEN_MSG)
    clean_reason = str(reason or "").strip() or "No reason provided"
    return (
        txt.replace("{user}", user_label or "Member")
        .replace("{ticket}", ticket_label or "ticket")
        .replace("{reason}", clean_reason)
        .replace("{server}", server_name or "Server")
        .replace("{claimer}", claimer or user_label or "Staff")
    )


def u_list(d, k):
    return d if isinstance(d, list) else (d.get(k, []) if isinstance(d, dict) else [])


def u_dict(d, k):
    return d.get(k, d) if isinstance(d, dict) and isinstance(d.get(k), dict) else (d if isinstance(d, dict) else {})


def get_scfg(sid):
    raw = None
    try:
        per = r_cmd("GET", f"ticketmint:cfg:{sid}")
        if per:
            raw = json.loads(per)
    except Exception:
        pass
    if raw is None:
        raw = load_all_cfg().get(str(sid), {})
    if not isinstance(raw, dict):
        raw = {"roles": raw} if isinstance(raw, list) else {}
    disabled = raw.get("disabled_cmds", [])
    roles = raw.get("roles", [])
    allowed_ping_roles = raw.get("allowed_ping_roles", [])
    protected_ping_roles = raw.get("protected_ping_roles", [])
    return {
        "roles": roles if isinstance(roles, list) else [],
        "allowed_ping_roles": allowed_ping_roles if isinstance(allowed_ping_roles, list) else [],
        "protected_ping_roles": protected_ping_roles if isinstance(protected_ping_roles, list) else [],
        "block_unpingable_roles": bool(raw.get("block_unpingable_roles", True)),
        "autorole": str(raw.get("autorole", "") or ""),
        "verify_role": str(raw.get("verify_role", "") or ""),
        "verify_channel": str(raw.get("verify_channel", "") or ""),
        "active_preset": str(raw.get("active_preset", "") or ""),
        "dash": str(raw.get("dash", "") or ""),
        "cat": str(raw.get("cat", "") or ""),
        "logs": str(raw.get("logs", "") or ""),
        "welcome": str(raw.get("welcome", "") or ""),
        "w_title": str(raw.get("w_title", "Welcome!") or "Welcome!"),
        "w_msg": str(raw.get("w_msg", "Welcome {user} to {server}! You are our {ordinal} member!") or "Welcome {user} to {server}! You are our {ordinal} member!"),
        "w_banner": str(raw.get("w_banner", "") or ""),
        "w_color": str(raw.get("w_color", "#ff7a00") or "#ff7a00"),
        "w_card": bool(raw.get("w_card", False)),
        "goodbye": str(raw.get("goodbye", "") or ""),
        "g_msg": str(raw.get("g_msg", "{user} just left {server}. We now have {member_count} members.") or "{user} just left {server}. We now have {member_count} members."),
        "disabled_cmds": disabled if isinstance(disabled, list) else [],
        "anti_link": bool(raw.get("anti_link", True)),
        "anti_caps": bool(raw.get("anti_caps", False)),
        "word_filter": bool(raw.get("word_filter", True)),
        "anti_spam": bool(raw.get("anti_spam", True)),
        "max_tickets": int(raw.get("max_tickets", 2) or 2),
        "ticket_cooldown": int(raw.get("ticket_cooldown", 30) or 0),
        "blocked_words": str(raw.get("blocked_words", "") or ""),
        "warn_word_msg": str(raw.get("warn_word_msg", "{user}, that word is not allowed here.") or "{user}, that word is not allowed here."),
        "warn_link_msg": str(raw.get("warn_link_msg", "{user}, links are not allowed in this channel.") or "{user}, links are not allowed in this channel."),
        "warn_role_ping_msg": str(raw.get("warn_role_ping_msg", "{user}, you cannot ping protected roles.") or "{user}, you cannot ping protected roles."),
        "announce_ping": str(raw.get("announce_ping", "") or ""),
        "announce_default_title": str(raw.get("announce_default_title", "Announcement") or "Announcement"),
        "announce_color": str(raw.get("announce_color", "#ff7a00") or "#ff7a00"),
        "announce_footer": str(raw.get("announce_footer", "") or ""),
        "ticket_open_msg": str(raw.get("ticket_open_msg", DEFAULT_OPEN_MSG) or DEFAULT_OPEN_MSG),
        "ticket_close_msg": str(raw.get("ticket_close_msg", DEFAULT_CLOSE_MSG) or DEFAULT_CLOSE_MSG),
        "ticket_claim_msg": str(raw.get("ticket_claim_msg", DEFAULT_CLAIM_MSG) or DEFAULT_CLAIM_MSG),
    }


def is_admin(sid, uid):
    if not sid or not uid:
        return False
    cache_key = f"tm:admin:{sid}:{uid}"
    try:
        cached = r_cmd("GET", cache_key)
        if cached in ("1", "0"):
            return cached == "1"
    except Exception:
        pass
    allowed = False
    try:
        srv = u_dict(safe_y("GET", f"/servers/{sid}"), "server")
        if str(srv.get("owner_id", "")) == str(uid):
            allowed = True
        else:
            mem = u_dict(safe_y("GET", f"/servers/{sid}/members/{uid}"), "member")
            mr = set(str(r) for r in (mem.get("roles", []) or []))
            for r in u_list(safe_y("GET", f"/servers/{sid}/roles"), "roles"):
                if isinstance(r, dict) and str(r.get("id")) in mr:
                    p = r.get("permissions", {})
                    if isinstance(p, dict) and (p.get("administrator") or p.get("manage_server") or p.get("manage_channels")):
                        allowed = True
                        break
    except Exception:
        allowed = False
    try:
        r_cmd("SET", cache_key, "1" if allowed else "0", "EX", "300")
    except Exception:
        pass
    return allowed


def post_panel(cid, sid=""):
    if not cid:
        return False, "Select a Ticket Panel Channel first."
    bname = u_dict(safe_y("GET", "/me"), "bot").get("name", "TicketMint")
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
    ok, err = post_raw_message(cid, payload)
    queued = queue_outbox({"type": "panel", "server_id": str(sid), "channel_id": str(cid)})
    if ok:
        return True, ""
    return (True, "") if queued else (False, err or "Could not post ticket panel.")


def post_verify_panel(cid, sname="Server", sid=""):
    if not cid:
        return False, "Select a Verification Channel first."
    bname = u_dict(safe_y("GET", "/me"), "bot").get("name", "TicketMint")
    payload = {
        "embeds": [{
            "title": f"Verify in {sname}",
            "description": "Click **Verify** below to confirm you're a real member and unlock the server.",
            "color": 0xFF7A00,
            "footer": {"text": f"{bname} • Member Verification"},
        }],
        "components": [{
            "type": 1,
            "components": [{"type": 2, "style": 1, "label": "Verify", "custom_id": "verify:claim"}],
        }],
    }
    ok, err = post_raw_message(cid, payload)
    queued = queue_outbox({"type": "verify_panel", "server_id": str(sid), "channel_id": str(cid), "server_name": sname})
    if ok:
        return True, ""
    return (True, "") if queued else (False, err or "Could not post verification panel.")


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0d12;color:#f3f4f6;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;min-height:100vh;display:flex;flex-direction:column}
a{text-decoration:none;color:inherit}
.nav{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border-bottom:1px solid #1c202b;background:#0e1118}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:19px;color:#fff;transition:transform .12s ease}
.brand:hover{transform:translateY(-1px)}
.badge{background:#ff7a00;color:#000;padding:3px 8px;border-radius:6px;font-weight:900;font-size:13px}
.nav-links{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn{padding:9px 15px;border-radius:8px;font-weight:700;font-size:13px;cursor:pointer;border:none;display:inline-flex;align-items:center;gap:6px;transition:transform .11s ease,background-color .12s ease,border-color .12s ease}
.btn:hover{transform:translateY(-1px)}
.btn:active{transform:translateY(1px) scale(.98)}
.btn-orange{background:#ff7a00;color:#000}
.btn-orange:hover{background:#ff8c24}
.btn-dark{background:#181c26;color:#fff;border:1px solid #282e3d}
.btn-dark:hover{background:#202634;border-color:#ff7a00}
.hero{max-width:820px;margin:48px auto;padding:0 18px;text-align:center}
.hero h1{font-size:clamp(28px,5vw,48px);line-height:1.12;margin-bottom:14px;font-weight:900}
.hero h1 span{color:#ff7a00}
.hero p{color:#9ca3af;font-size:16px;max-width:560px;margin:0 auto 24px;line-height:1.5}
.hero-btns{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;max-width:940px;margin:28px auto;padding:0 18px}
.card{background:#12151e;border:1px solid #1f2432;border-radius:12px;padding:18px;transition:transform .13s ease,border-color .13s ease}
.card:hover{transform:translateY(-2px);border-color:#ff7a00}
.srv-row{display:flex;align-items:center;justify-content:space-between;background:#12151e;border:1px solid #1f2432;border-radius:12px;padding:15px 18px;margin-bottom:10px;transition:transform .11s ease,border-color .13s ease,background-color .13s ease}
.srv-row:hover{transform:translateX(3px);border-color:#ff7a00;background:#161a26}
.srv-row:active{transform:scale(.99)}
.srv-left{display:flex;align-items:center;gap:14px}
.srv-ico{width:42px;height:42px;border-radius:10px;background:#1b2030;border:1px solid #2a3147;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:17px;color:#fff;overflow:hidden;flex-shrink:0}
.srv-ico img{width:100%;height:100%;object-fit:cover}
.wrap{max-width:960px;width:100%;margin:24px auto;padding:0 16px;flex:1}
.layout{display:grid;grid-template-columns:215px 1fr;gap:18px}
@media(max-width:740px){.layout{grid-template-columns:1fr}}
.side{background:#12151e;border:1px solid #1f2432;border-radius:12px;padding:10px;height:fit-content}
.side button.tab-btn,.side button.side-btn{display:block;width:100%;text-align:left;background:transparent;border:none;font-family:inherit;cursor:pointer;padding:10px 12px;border-radius:8px;color:#9ca3af;font-weight:600;margin-bottom:3px;font-size:13px;transition:transform .1s ease,background-color .1s ease,color .1s ease}
.side button.tab-btn:hover,.side button.side-btn:hover{color:#fff;background:#181c28;transform:translateX(2px)}
.side button.tab-btn:active,.side button.side-btn:active{transform:scale(.98)}
.side button.tab-btn.act{background:#ff7a0022;color:#ff7a00;border-left:3px solid #ff7a00}
.side hr{border:none;border-top:1px solid #1c202b;margin:7px 0}
.panel{background:#12151e;border:1px solid #1f2432;border-radius:12px;padding:20px}
.tab-pane{display:none}
.tab-pane.act{display:block}
.field{padding:15px 0;border-bottom:1px solid #1c202b}
.field:last-child{border-bottom:none}
.field label{display:block;font-weight:700;margin-bottom:4px;font-size:14px}
.field small{display:block;color:#9ca3af;margin-bottom:8px;font-size:12px}
select,input[type=text],input[type=number],textarea{width:100%;padding:10px 11px;border-radius:8px;background:#0b0d12;color:#fff;border:1px solid #2a3040;font-size:13px;font-family:inherit;transition:border-color .12s ease}
select:focus,input:focus,textarea:focus{outline:none;border-color:#ff7a00}
textarea{min-height:96px;resize:vertical}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:600px){.row2{grid-template-columns:1fr}}
.pills{display:flex;flex-wrap:wrap;gap:7px}
.pill input{display:none}
.pill span{display:inline-block;padding:6px 12px;border-radius:999px;background:#0b0d12;border:1px solid #2a3040;font-size:12px;font-weight:600;cursor:pointer;color:#cbd5e1;transition:transform .1s ease,background-color .12s ease,border-color .12s ease}
.pill span:hover{transform:translateY(-1px);border-color:#ff7a00}
.pill span:active{transform:scale(.96)}
.pill input:checked+span{background:#ff7a00;color:#000;border-color:#ff7a00}
.cmd-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 12px;border-radius:9px;background:#0b0d12;border:1px solid #1f2432;margin-bottom:8px;transition:border-color .12s ease}
.cmd-row:hover{border-color:#2e364a}
.cmd-row.active-preset{border-color:#ff7a00}
.chk-line{display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600;font-size:13px}
.chk-line input{width:16px;height:16px;accent-color:#ff7a00}
.preview-box{background:#0b0d12;border:1px solid #242a3a;border-left:4px solid #ff7a00;border-radius:9px;padding:12px 14px;margin-top:8px}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}
@media(max-width:560px){.stats-grid{grid-template-columns:repeat(2,1fr)}}
.stat-box{background:#0b0d12;border:1px solid #1f2432;border-radius:9px;padding:11px}
.stat-num{font-size:20px;font-weight:900;color:#ff7a00}
.stat-lbl{font-size:11px;color:#9ca3af;margin-top:2px}
.active-pill{background:#ff7a0026;color:#ff7a00;border:1px solid #ff7a00;padding:2px 7px;border-radius:999px;font-size:10px;font-weight:800;margin-left:6px}
.perm-tag{display:inline-block;padding:2px 7px;border-radius:999px;font-size:10px;font-weight:800;margin-left:6px}
.perm-mod{background:#ef444422;color:#f87171;border:1px solid #ef444466}
.perm-mem{background:#22c55e22;color:#4ade80;border:1px solid #22c55e66}
.tm-toast{transition:opacity .35s ease,transform .35s ease}
.tm-toast.hide{opacity:0;transform:translateY(-4px);pointer-events:none}
"""

INSTANT_JS = """
<script>
function tmSwitchTab(tabName){
  var panes=document.querySelectorAll('.tab-pane');
  var btns=document.querySelectorAll('.tab-btn');
  for(var i=0;i<panes.length;i++){
    panes[i].classList.toggle('act',panes[i].getAttribute('data-pane')===tabName);
  }
  for(var j=0;j<btns.length;j++){
    btns[j].classList.toggle('act',btns[j].getAttribute('data-tab')===tabName);
  }
  document.querySelectorAll('form input[name="tab"]').forEach(function(inp){inp.value=tabName;});
  try{
    var url=new URL(window.location.href);
    url.searchParams.set('tab',tabName);
    window.history.replaceState({},'',url.toString());
  }catch(e){}
}
function tmCycleRoleSelect(selId, statusId){
  var sel=document.getElementById(selId);
  if(!sel||!sel.options.length)return;
  sel.selectedIndex=(sel.selectedIndex+1)%sel.options.length;
  var st=document.getElementById(statusId);
  if(st){st.textContent='Selected Ping Role: '+sel.options[sel.selectedIndex].textContent;}
}
document.addEventListener('submit',function(e){
  var f=e.target;
  if(!f||f.tagName!=='FORM')return;
  var sub=e.submitter||f.querySelector('button[type=submit],button:not([type=button])');
  if(sub&&!sub.dataset.busy){
    sub.dataset.busy='1';
    sub.style.opacity='0.75';
  }
});
window.addEventListener('DOMContentLoaded',function(){
  var toast=document.getElementById('tm-notice');
  if(toast){
    setTimeout(function(){
      toast.classList.add('hide');
      setTimeout(function(){if(toast&&toast.parentNode)toast.parentNode.removeChild(toast);},380);
    },7000);
    try{
      var url=new URL(window.location.href);
      ['synced','saved','sent','err'].forEach(function(k){url.searchParams.delete(k);});
      window.history.replaceState({},'',url.toString());
    }catch(e){}
  }
});
</script>
"""


def page(title, body, user=None):
    inv = f"<a href='{INVITE_URL}' class='btn btn-dark'>+ Invite Bot</a>"
    right = (
        f"{inv} <a href='/dashboard' class='btn btn-dark'>@{esc(user['username'])}</a> <a href='/logout' class='btn btn-dark'>Logout</a>"
        if user
        else f"{inv} <a href='/login' class='btn btn-orange'>Authorize with Yapin'</a>"
    )
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
        f"<div class='nav'><a href='/' class='brand'><span class='badge'>TM</span> TicketMint</a><div class='nav-links'>{right}</div></div>"
        f"{body}{INSTANT_JS}</body></html>"
    )


def decode_jwt(tok):
    try:
        parts = str(tok).split(".")
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
            parsed = json.loads(raw) if raw else None
            return parsed if isinstance(parsed, dict) and parsed.get("id") else None
        except Exception:
            return None

    def send_html(self, html_body, cookie=None):
        out = html_body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(out)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(out)

    def redir(self, loc, cookie=None):
        self.send_response(302)
        self.send_header("Location", loc)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def do_GET(self):
        try:
            self._handle_get()
        except Exception as e:
            self.send_html(
                page("Dashboard Error", f"<div class='wrap'><div class='panel'><h2 style='color:#ff7a00'>Something went wrong</h2><p style='color:#9ca3af;margin-top:8px'>{esc(clean_err(e))}</p><div style='margin-top:14px'><a href='/dashboard' class='btn btn-orange'>Back to Servers</a></div></div></div>")
            )

    def _handle_get(self):
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
                        {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"},
                    ),
                    (
                        json.dumps({
                            "client_id": CLIENT_ID,
                            "client_secret": CLIENT_SECRET,
                            "grant_type": "authorization_code",
                            "code": code,
                            "redirect_uri": REDIR_URI,
                        }).encode("utf-8"),
                        {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                    ),
                ]
                for b_data, hdrs in attempts:
                    try:
                        req = urllib.request.Request(OAUTH_TOKEN, data=b_data, headers=hdrs, method="POST")
                        tok_data = json.loads(urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))
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
                                headers={"Authorization": f"Bearer {access}", "User-Agent": "Mozilla/5.0"},
                            )
                            cand = json.loads(urllib.request.urlopen(me_req, timeout=5).read().decode("utf-8"))
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
                    parsed = json.loads(cached)
                    if isinstance(parsed, list):
                        all_srvs = parsed
            except Exception:
                pass
            if not all_srvs:
                for sp in ("/servers", "/me"):
                    res = safe_y("GET", sp)
                    cand = u_list(res, "servers") or (res.get("bot", {}).get("servers", []) if isinstance(res, dict) and isinstance(res.get("bot"), dict) else [])
                    for c in cand:
                        if isinstance(c, dict) and c.get("id") and not any(str(x.get("id")) == str(c.get("id")) for x in all_srvs):
                            all_srvs.append(c)
                if all_srvs:
                    try:
                        r_cmd("SET", "ticketmint:servers", json.dumps(all_srvs), "EX", "120")
                    except Exception:
                        pass
            admin_srvs = [
                s for s in all_srvs
                if isinstance(s, dict) and (
                    not s.get("owner_id")
                    or str(s.get("owner_id")) == str(sess["id"])
                    or s.get("owner") is True
                    or is_admin(s.get("id"), sess["id"])
                )
            ]
            sel_id = qs.get("server", [""])[0].strip()
            if not sel_id:
                rows = []
                for s in admin_srvs:
                    sname = pick_name(s, "Server")
                    ico = f"<img src='{esc(s['icon'])}' loading='lazy' alt=''>" if s.get("icon") else esc(sname[:1].upper())
                    mc = f"{s['member_count']} members" if s.get("member_count") else "Ready to configure"
                    rows.append(
                        f"<a href='/dashboard?server={esc(s['id'])}' class='srv-row'>"
                        f"<div class='srv-left'><div class='srv-ico'>{ico}</div><div>"
                        f"<h3 style='font-size:16px;margin-bottom:2px'>{esc(sname)}</h3>"
                        f"<small style='color:#9ca3af'>{esc(mc)}</small></div></div>"
                        f"<span style='color:#ff7a00;font-weight:700;font-size:13px'>Configure &rarr;</span></a>"
                    )
                cards = "".join(rows)
                add_box = (
                    f"<div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><a href='{INVITE_URL}' class='btn btn-orange'>+ Invite TicketMint to Server</a></div>"
                    f"<form method='GET' action='/dashboard' style='display:flex;gap:10px;max-width:440px;margin-top:16px'>"
                    f"<input type='text' name='server' placeholder='Or paste Server ID directly...' required>"
                    f"<button class='btn btn-dark' type='submit'>Open</button></form>"
                )
                empty = f"<div class='panel'><p style='margin-bottom:8px'>Add <b>TicketMint</b> to your server to configure it here.</p>{add_box}</div>"
                footer_inv = f"<div style='text-align:center;margin-top:18px'><a href='{INVITE_URL}' class='btn btn-dark'>+ Invite TicketMint to Another Server</a></div>" if cards else ""
                return self.send_html(
                    page("Select Server - TicketMint", f"<div class='wrap' style='max-width:740px'><div style='text-align:center;margin:16px 0 26px'><h1 style='font-size:30px;margin-bottom:4px'>Hey, {esc(sess['username'])}</h1><p style='color:#9ca3af'>Pick a server to configure.</p></div>{cards if cards else empty}{footer_inv}</div>", sess)
                )

            srv_obj = next((s for s in admin_srvs if str(s.get("id")) == str(sel_id)), None)
            meta = {}
            try:
                mraw = r_cmd("GET", f"ticketmint:meta:{sel_id}")
                if mraw:
                    parsed_m = json.loads(mraw)
                    if isinstance(parsed_m, dict):
                        meta = parsed_m
            except Exception:
                pass

            need_refresh = bool(qs.get("refresh")) or not meta.get("channels")
            fetched = {}
            if need_refresh:
                meta, fetched = sync_server_metadata(sel_id, meta)
            elif not srv_obj:
                srv_full = safe_y("GET", f"/servers/{sel_id}")
                fetched = u_dict(srv_full, "server")
                if isinstance(fetched, dict) and fetched.get("id") and not is_admin(sel_id, sess["id"]):
                    return self.redir("/dashboard")

            base_srv = srv_obj if isinstance(srv_obj, dict) else (fetched if isinstance(fetched, dict) and fetched.get("id") else {"id": sel_id})
            srv_name = resolve_server_name(sel_id, fetched=fetched, base_srv=base_srv, meta=meta)
            m_count = (fetched.get("member_count") if isinstance(fetched, dict) else None) or base_srv.get("member_count") or 5
            sc = get_scfg(sel_id)
            tab = qs.get("tab", ["tickets"])[0].strip().lower()
            valid_tabs = ("tickets", "welcome", "announce", "automod", "verification", "commands", "presets")
            if tab not in valid_tabs:
                tab = "tickets"

            roles = meta.get("roles", []) if isinstance(meta.get("roles"), list) else []
            chs = meta.get("channels", []) if isinstance(meta.get("channels"), list) else []
            cat_chs = meta.get("categories", []) if isinstance(meta.get("categories"), list) else []

            txt_chs = [c for c in chs if isinstance(c, dict) and not is_cat_item(c) and not is_voice_item(c)]
            if not txt_chs:
                txt_chs = [c for c in chs if isinstance(c, dict) and not is_cat_item(c)]

            def ch_opts(items, selected_id, empty_label, prefix="#"):
                out = [f"<option value=''>{esc(empty_label)}</option>"]
                for c in items:
                    if not isinstance(c, dict):
                        continue
                    cid = str(c.get("id", ""))
                    cname = c.get("name", "channel")
                    out.append(f"<option value='{esc(cid)}' {'selected' if cid == str(selected_id) else ''}>{esc(prefix)}{esc(cname)}</option>")
                return "".join(out)

            notice = ""
            if qs.get("synced"):
                notice = "<div id='tm-notice' class='tm-toast' style='background:#16a34a22;border:1px solid #16a34a;color:#4ade80;padding:9px 13px;border-radius:8px;margin-bottom:14px;font-size:13px'>Synced channels, roles &amp; categories!</div>"
            elif qs.get("saved"):
                notice = "<div id='tm-notice' class='tm-toast' style='background:#16a34a22;border:1px solid #16a34a;color:#4ade80;padding:9px 13px;border-radius:8px;margin-bottom:14px;font-size:13px'>Saved changes!</div>"
            elif qs.get("sent"):
                notice = "<div id='tm-notice' class='tm-toast' style='background:#16a34a22;border:1px solid #16a34a;color:#4ade80;padding:9px 13px;border-radius:8px;margin-bottom:14px;font-size:13px'>Announcement / action was sent!</div>"
            elif qs.get("err"):
                notice = f"<div id='tm-notice' class='tm-toast' style='background:#dc262622;border:1px solid #dc2626;color:#f87171;padding:9px 13px;border-radius:8px;margin-bottom:14px;font-size:13px'>{esc(clean_err(qs.get('err', ['Error'])[0]))}</div>"

            active_cmds = len(ALL_COMMANDS) - len(set(sc["disabled_cmds"]))
            stats_bar = (
                f"<div class='stats-grid'>"
                f"<div class='stat-box'><div class='stat-num'>{len(sc['roles'])}</div><div class='stat-lbl'>Mod Roles</div></div>"
                f"<div class='stat-box'><div class='stat-num'>{len(txt_chs)}</div><div class='stat-lbl'>Text Channels</div></div>"
                f"<div class='stat-box'><div class='stat-num'>{len(cat_chs)}</div><div class='stat-lbl'>Categories</div></div>"
                f"<div class='stat-box'><div class='stat-num'>{active_cmds}/{len(ALL_COMMANDS)}</div><div class='stat-lbl'>Commands</div></div>"
                f"</div>"
            )

            non_everyone_roles = [r for r in roles if isinstance(r, dict) and r.get("name") != "@everyone"]
            pills = "".join(
                f"<label class='pill'><input type='checkbox' name='roles' value='{esc(r['id'])}' {'checked' if str(r['id']) in set(str(x) for x in sc['roles']) else ''}><span>{esc(r.get('name', 'Role'))}</span></label>"
                for r in non_everyone_roles
            ) or "<span style='color:#9ca3af;font-size:12px'>Click Sync Channels &amp; Roles if roles don't appear yet.</span>"

            allowed_ping_pills = "".join(
                f"<label class='pill'><input type='checkbox' name='allowed_ping_roles' value='{esc(r['id'])}' {'checked' if str(r['id']) in set(str(x) for x in sc['allowed_ping_roles']) else ''}><span>@{esc(r.get('name', 'Role'))}</span></label>"
                for r in non_everyone_roles
            ) or "<span style='color:#9ca3af;font-size:12px'>No roles synced yet.</span>"

            protected_ping_pills = "".join(
                f"<label class='pill'><input type='checkbox' name='protected_ping_roles' value='{esc(r['id'])}' {'checked' if str(r['id']) in set(str(x) for x in sc['protected_ping_roles']) else ''}><span>@{esc(r.get('name', 'Role'))}</span></label>"
                for r in non_everyone_roles
            ) or "<span style='color:#9ca3af;font-size:12px'>No roles synced yet.</span>"

            def role_ping_opts(selected_val):
                sel_s = str(selected_val or "").strip()
                out = [f"<option value='' {'selected' if sel_s == '' else ''}>No Role Ping</option>"]
                out.append(f"<option value='@everyone' {'selected' if sel_s.lower() in ('everyone', '@everyone') else ''}>@everyone</option>")
                for r in non_everyone_roles:
                    if not isinstance(r, dict) or not r.get("id"):
                        continue
                    rid = str(r["id"])
                    rname = str(r.get("name") or rid)
                    is_sel = sel_s in (rid, f"<@&{rid}>", f"@{rname}", rname)
                    out.append(f"<option value='{esc(rid)}' {'selected' if is_sel else ''}>@{esc(rname)}</option>")
                return "".join(out)

            cho = ch_opts(txt_chs, sc["dash"], "-- Select Ticket Panel Channel --", "#")
            cao = ch_opts(cat_chs, sc["cat"], "None (Optional)", "")
            lgo = ch_opts(txt_chs, sc["logs"], "None (Optional)", "#")
            open_prev = esc(format_ticket_log_message(sc["ticket_open_msg"], f"@{sess['username']}", "#ticket-1898", "Need help with setup", srv_name, f"@{sess['username']}"))
            close_prev = esc(format_ticket_log_message(sc["ticket_close_msg"], f"@{sess['username']}", "#ticket-1898", "Issue solved", srv_name, f"@{sess['username']}"))

            tickets_pane = (
                f"<div class='tab-pane {'act' if tab=='tickets' else ''}' data-pane='tickets'>{stats_bar}"
                f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div class='field'><label>Admin / Mod Roles ({len(sc['roles'])} selected)</label><small>Members with these roles can use mod-only commands and view/claim/close tickets.</small><div class='pills'>{pills}</div></div>"
                f"<div class='field'><label>Roles Members CAN Ping</label><small>Roles that regular members are allowed to ping.</small><div class='pills'>{allowed_ping_pills}</div></div>"
                f"<div class='field'><label>Protected Roles Members CANNOT Ping</label><small>If a non-staff member pings any selected role, TicketMint blocks/warns on it.</small>"
                f"<div class='pills'>{protected_ping_pills}</div>"
                f"<div style='margin-top:10px'><label class='chk-line'><input type='checkbox' name='block_unpingable_roles' value='1' {'checked' if sc['block_unpingable_roles'] else ''}><span>Enforce protected role ping blocking for regular members</span></label></div>"
                f"<div style='margin-top:10px'><label>Protected Role Warning Message</label><small>Sent when a member pings a protected role. Use <b>{{user}}</b>.</small><input type='text' name='warn_role_ping_msg' value='{esc(sc['warn_role_ping_msg'])}' placeholder='{{user}}, you cannot ping protected roles.'></div></div>"
                f"<div class='field'><label>Ticket Panel Channel</label><small>Channel where the Open a Ticket dashboard gets posted.</small><select name='dash'>{cho}</select></div>"
                f"<div class='field'><label>Ticket Category (Optional)</label><small>Category where new private ticket rooms are placed.</small><select name='cat'>{cao}</select></div>"
                f"<div class='field'><label>Ticket Logs &amp; Transcripts Channel (Optional)</label><small>Receives custom open &amp; close ticket logs and transcripts.</small><select name='logs'>{lgo}</select></div>"
                f"<div class='field'><label>Ticket Reason (For Test Open / Close Log)</label><small>Enter a ticket reason to include in the test ticket log.</small>"
                f"<input type='text' name='ticket_test_reason' value='Support • General Inquiry' placeholder='Type ticket reason...'></div>"
                f"<div class='field'><label>Ticket Opened Log Message (Editable)</label><small>Variables: <b>{{user}}</b>, <b>{{ticket}}</b>, <b>{{reason}}</b>, <b>{{server}}</b>.</small>"
                f"<input type='text' name='ticket_open_msg' value='{esc(sc['ticket_open_msg'])}' placeholder='{esc(DEFAULT_OPEN_MSG)}'>"
                f"<div class='preview-box' style='border-left-color:#22c55e'><div style='font-size:10px;color:#9ca3af;margin-bottom:3px'>OPEN LOG PREVIEW</div><div style='font-size:13px'>{open_prev}</div></div></div>"
                f"<div class='field'><label>Ticket Closed Log Message (Editable)</label><small>Variables: <b>{{user}}</b>, <b>{{ticket}}</b>, <b>{{reason}}</b>, <b>{{claimer}}</b>, <b>{{server}}</b>.</small>"
                f"<input type='text' name='ticket_close_msg' value='{esc(sc['ticket_close_msg'])}' placeholder='{esc(DEFAULT_CLOSE_MSG)}'>"
                f"<div class='preview-box' style='border-left-color:#ef4444'><div style='font-size:10px;color:#9ca3af;margin-bottom:3px'>CLOSE LOG PREVIEW</div><div style='font-size:13px'>{close_prev}</div></div></div>"
                f"<div style='display:flex;gap:8px;flex-wrap:wrap;padding-top:14px'>"
                f"<button type='submit' name='act' value='save' class='btn btn-orange'>Save Changes</button>"
                f"<button type='submit' name='act' value='post' class='btn btn-dark'>Save &amp; Post Ticket Panel</button>"
                f"<button type='submit' name='act' value='modping' class='btn btn-dark'>Send Staff Ping</button>"
                f"<button type='submit' name='act' value='test_ticket_open' class='btn btn-dark'>Test Open Log</button>"
                f"<button type='submit' name='act' value='test_ticket_close' class='btn btn-dark'>Test Close Log</button></div></form></div>"
            )

            w_cho = ch_opts(txt_chs, sc["welcome"], "Disabled (No Welcome Channel)", "#")
            g_cho = ch_opts(txt_chs, sc["goodbye"], "Disabled (No Goodbye Channel)", "#")
            ar_cho = ch_opts(non_everyone_roles, sc["autorole"], "Disabled (No Auto-Role)", "@")
            prev_col = sc["w_color"] if str(sc["w_color"]).startswith("#") else "#ff7a00"
            prev_txt = (
                esc(sc["w_msg"])
                .replace("{user}", f"@{esc(sess['username'])}")
                .replace("{server}", esc(srv_name))
                .replace("{member_count}", str(m_count))
                .replace("{ordinal}", ordinal_num(m_count))
            )
            banner_prev = f"<img src='{esc(sc['w_banner'])}' loading='lazy' style='width:100%;max-height:140px;object-fit:cover;border-radius:7px;margin-top:8px' alt=''>" if sc["w_banner"] else ""
            welcome_pane = (
                f"<div class='tab-pane {'act' if tab=='welcome' else ''}' data-pane='welcome'>"
                f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div class='field row2'><div><label>Welcome Channel</label><small>Pings new members and posts their welcome message.</small><select name='welcome'>{w_cho}</select></div>"
                f"<div><label>Auto-Role on Join (Optional)</label><small>Automatically assign a starter role to new members.</small><select name='autorole'>{ar_cho}</select></div></div>"
                f"<div class='field row2'><div><label>Welcome Embed Title</label><small>Heading shown at the top of the welcome card.</small><input type='text' name='w_title' value='{esc(sc['w_title'])}' placeholder='Welcome!'></div>"
                f"<div><label>Accent Color (Hex)</label><small>Default TicketMint orange is #ff7a00.</small><input type='text' name='w_color' value='{esc(sc['w_color'])}' placeholder='#ff7a00'></div></div>"
                f"<div class='field'><label>Welcome Message</label><small>Supports <b>{{user}}</b> (ping), <b>{{server}}</b>, <b>{{ordinal}}</b> (e.g. 5th), and <b>{{member_count}}</b>.</small><input type='text' name='w_msg' value='{esc(sc['w_msg'])}' placeholder='Welcome {{user}} to {{server}}! You are our {{ordinal}} member!'></div>"
                f"<div class='field'><label class='chk-line'><input type='checkbox' name='w_card' value='1' {'checked' if sc['w_card'] else ''}><span>Send generated PNG Welcome Image Card with user's avatar &amp; member #</span></label></div>"
                f"<div class='field'><label>Welcome Banner Image URL (Optional)</label><small>Used when PNG Welcome Card mode is unchecked.</small><input type='text' name='w_banner' value='{esc(sc['w_banner'])}' placeholder='https://...'>"
                f"<div class='preview-box' style='border-left-color:{esc(prev_col)}'><div style='font-size:10px;color:#9ca3af;margin-bottom:4px'>LIVE PREVIEW</div>"
                f"<div style='font-weight:800;font-size:14px;margin-bottom:3px'>{esc(sc['w_title'] or 'Welcome!')}</div>"
                f"<div style='color:#cbd5e1;font-size:13px'>{prev_txt}</div>{banner_prev}</div></div>"
                f"<div class='field'><label>Goodbye Channel (Optional)</label><small>Channel where goodbye messages are posted when a member leaves.</small><select name='goodbye'>{g_cho}</select></div>"
                f"<div class='field'><label>Goodbye Message</label><small>Supports <b>{{user}}</b>, <b>{{server}}</b>, and <b>{{member_count}}</b>.</small><input type='text' name='g_msg' value='{esc(sc['g_msg'])}' placeholder='{{user}} just left {{server}}. We now have {member_count} members.'></div>"
                f"<div style='display:flex;gap:8px;flex-wrap:wrap;padding-top:14px'>"
                f"<button type='submit' name='act' value='save' class='btn btn-orange'>Save Welcome &amp; Goodbye</button>"
                f"<button type='submit' name='act' value='test_welcome' class='btn btn-dark'>Send Test Welcome Card</button></div></form></div>"
            )

            ann_cho = ch_opts(txt_chs, sc["dash"], "-- Select Target Channel --", "#")
            ann_role_opts = role_ping_opts(sc["announce_ping"])
            announce_pane = (
                f"<div class='tab-pane {'act' if tab=='announce' else ''}' data-pane='announce'>"
                f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div class='field'><label>Target Channel</label><small>Choose where TicketMint should post this announcement.</small><select name='ann_channel' required>{ann_cho}</select></div>"
                f"<div class='field row2'><div><label>Announcement Title</label><small>Displayed as a bold heading.</small><input type='text' name='ann_title' value='{esc(sc['announce_default_title'])}' placeholder='Server Update!' required></div>"
                f"<div><label>Select Role to Ping</label><small>Pick a role or @everyone to ping with this announcement.</small>"
                f"<div style='display:flex;gap:8px;align-items:center'><select id='annRoleSelect' name='ann_role_select' style='flex:1'>{ann_role_opts}</select>"
                f"<button type='button' class='btn btn-dark' onclick=\"tmCycleRoleSelect('annRoleSelect','annRoleStatus')\">Select Role to Ping</button></div>"
                f"<div id='annRoleStatus' style='color:#9ca3af;font-size:11px;margin-top:5px'>Or type custom ping below ({esc(sc['announce_ping'] or 'none')}).</div>"
                f"<input type='text' name='ann_custom_ping' value='{esc(sc['announce_ping'])}' placeholder='@RoleName or role ID (optional override)' style='margin-top:6px'></div></div>"
                f"<div class='field'><label>Announcement Message</label><small>Write your announcement details below.</small><textarea name='ann_body' placeholder='Hey everyone! Here is what is new...' required></textarea></div>"
                f"<div class='field'><label class='chk-line'><input type='checkbox' name='ann_everyone' value='1'><span>Override with @everyone above the announcement</span></label></div>"
                f"<div style='display:flex;gap:8px;flex-wrap:wrap;padding-top:14px'><button type='submit' name='act' value='announce' class='btn btn-orange'>Send Announcement</button></div></form></div>"
            )

            automod_pane = (
                f"<div class='tab-pane {'act' if tab=='automod' else ''}' data-pane='automod'>"
                f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div class='field'><label>Chat &amp; Ticket Protection</label><small>Simple, effective protection against spam, links, caps, and bad words.</small>"
                f"<div class='cmd-row'><div><div style='font-weight:700;font-size:13px'>Anti-Link Guard</div><div style='color:#9ca3af;font-size:12px;margin-top:2px'>Block external links from non-staff members</div></div>"
                f"<label class='pill'><input type='checkbox' name='anti_link' value='1' {'checked' if sc['anti_link'] else ''}><span>Active</span></label></div>"
                f"<div class='cmd-row'><div><div style='font-weight:700;font-size:13px'>Smart Word Filter</div><div style='color:#9ca3af;font-size:12px;margin-top:2px'>Catches stretched letters, leetspeak, and custom banned words + warns privately</div></div>"
                f"<label class='pill'><input type='checkbox' name='word_filter' value='1' {'checked' if sc['word_filter'] else ''}><span>Active</span></label></div>"
                f"<div class='cmd-row'><div><div style='font-weight:700;font-size:13px'>Anti-Spam Flood Guard</div><div style='color:#9ca3af;font-size:12px;margin-top:2px'>Stops users sending 5+ rapid messages within 6 seconds</div></div>"
                f"<label class='pill'><input type='checkbox' name='anti_spam' value='1' {'checked' if sc['anti_spam'] else ''}><span>Active</span></label></div>"
                f"<div class='cmd-row'><div><div style='font-weight:700;font-size:13px'>Excessive Caps Guard</div><div style='color:#9ca3af;font-size:12px;margin-top:2px'>Cleans up long ALL-CAPS messages</div></div>"
                f"<label class='pill'><input type='checkbox' name='anti_caps' value='1' {'checked' if sc['anti_caps'] else ''}><span>Active</span></label></div></div>"
                f"<div class='field'><label>Banned Words (Comma Separated)</label><small>Leave blank for default filter, or add custom words: word1, word2</small><input type='text' name='blocked_words' value='{esc(sc['blocked_words'])}' placeholder='word1, word2, word3'></div>"
                f"<div class='field row2'><div><label>Private Banned Word Warning Message</label><small>Sent privately to the user. Use <b>{{user}}</b>.</small><input type='text' name='warn_word_msg' value='{esc(sc['warn_word_msg'])}' placeholder='{{user}}, that word is not allowed here.'></div>"
                f"<div><label>Link Warning Message</label><small>Sent to the user. Use <b>{{user}}</b>.</small><input type='text' name='warn_link_msg' value='{esc(sc['warn_link_msg'])}' placeholder='{{user}}, links are not allowed in this channel.'></div></div>"
                f"<div class='field row2'><div><label>Max Open Tickets Per User</label><small>Prevent users from opening too many rooms at once.</small><input type='number' name='max_tickets' min='1' max='10' value='{esc(sc['max_tickets'])}'></div>"
                f"<div><label>Ticket Cooldown (Seconds)</label><small>Wait time between opening tickets (0 = off).</small><input type='number' name='ticket_cooldown' min='0' max='3600' value='{esc(sc['ticket_cooldown'])}'></div></div>"
                f"<div style='display:flex;gap:8px;flex-wrap:wrap;padding-top:14px'><button type='submit' name='act' value='save' class='btn btn-orange'>Save Protection Rules</button></div></form></div>"
            )

            vr_cho = ch_opts(non_everyone_roles, sc["verify_role"], "Disabled (No Verified Role)", "@")
            vc_cho = ch_opts(txt_chs, sc["verify_channel"], "-- Select Verification Channel --", "#")
            verification_pane = (
                f"<div class='tab-pane {'act' if tab=='verification' else ''}' data-pane='verification'>"
                f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div class='field row2'><div><label>Verified Role</label><small>Role given when a member clicks Verify.</small><select name='verify_role'>{vr_cho}</select></div>"
                f"<div><label>Verification Channel</label><small>Channel where the Verify button panel is posted.</small><select name='verify_channel'>{vc_cho}</select></div></div>"
                f"<div class='preview-box'><div style='font-size:10px;color:#9ca3af;margin-bottom:4px'>PANEL PREVIEW</div>"
                f"<div style='font-weight:800;font-size:14px;margin-bottom:4px'>Verify in {esc(srv_name)}</div>"
                f"<div style='color:#cbd5e1;font-size:13px;margin-bottom:10px'>Click Verify to unlock member channels.</div>"
                f"<span class='btn btn-orange' style='pointer-events:none'>Verify</span></div>"
                f"<div style='display:flex;gap:8px;flex-wrap:wrap;padding-top:14px'>"
                f"<button type='submit' name='act' value='save' class='btn btn-orange'>Save Verification</button>"
                f"<button type='submit' name='act' value='post_verify' class='btn btn-dark'>Save &amp; Post Verify Panel</button></div></form></div>"
            )

            ap = sc.get("active_preset", "")
            def p_badge(code):
                return "<span class='active-pill'>ACTIVE</span>" if ap == code else ""
            def p_btn_cls(code):
                return "btn-orange" if ap == code else "btn-dark"
            presets_pane = (
                f"<div class='tab-pane {'act' if tab=='presets' else ''}' data-pane='presets'>"
                f"<div class='field'><label>1-Click Setup Presets</label><small>Apply recommended settings for your community in one click.</small>"
                f"<form method='POST' action='/save' class='cmd-row {'active-preset' if ap=='preset_gaming' else ''}'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div><div style='font-weight:700;font-size:13px'>Gaming Community{p_badge('preset_gaming')}</div><div style='color:#9ca3af;font-size:12px'>Balanced anti-link + word filter, welcome cards enabled, 2 max tickets</div></div>"
                f"<button type='submit' name='act' value='preset_gaming' class='btn {p_btn_cls('preset_gaming')}'>{'Applied' if ap=='preset_gaming' else 'Apply'}</button></form>"
                f"<form method='POST' action='/save' class='cmd-row {'active-preset' if ap=='preset_strict' else ''}'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div><div style='font-weight:700;font-size:13px'>Strict Safe Chat{p_badge('preset_strict')}</div><div style='color:#9ca3af;font-size:12px'>Anti-link + anti-spam + word filter active, 60s ticket cooldown, 1 max ticket</div></div>"
                f"<button type='submit' name='act' value='preset_strict' class='btn {p_btn_cls('preset_strict')}'>{'Applied' if ap=='preset_strict' else 'Apply'}</button></form>"
                f"<form method='POST' action='/save' class='cmd-row {'active-preset' if ap=='preset_chill' else ''}'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div><div style='font-weight:700;font-size:13px'>Chill / Open Server{p_badge('preset_chill')}</div><div style='color:#9ca3af;font-size:12px'>Links allowed, word filter + anti-spam active, fast 15s ticket cooldown</div></div>"
                f"<button type='submit' name='act' value='preset_chill' class='btn {p_btn_cls('preset_chill')}'>{'Applied' if ap=='preset_chill' else 'Apply'}</button></form></div></div>"
            )

            disabled = set(sc["disabled_cmds"])
            cmd_items = "".join(
                f"<div class='cmd-row'><div><div style='font-weight:700;font-size:13px'>{esc(label)}"
                f"<span class='perm-tag {'perm-mod' if mod_only else 'perm-mem'}'>{'MODS ONLY' if mod_only else 'MEMBERS'}</span></div>"
                f"<div style='color:#9ca3af;font-size:12px;margin-top:2px'>{esc(desc)}</div></div>"
                f"<label class='pill'><input type='checkbox' name='enabled_cmds' value='{esc(key)}' {'checked' if key not in disabled else ''}><span>Enabled</span></label></div>"
                for key, label, desc, mod_only in ALL_COMMANDS
            )
            run_cmd_opts = "".join(
                f"<option value='{esc(key)}'>{esc(label)}</option>"
                for key, label, _, _ in ALL_COMMANDS
            )
            run_ch_opts = ch_opts(txt_chs, sc["dash"], "-- Select Channel --", "#")
            cmd_role_opts = role_ping_opts(sc["announce_ping"])
            commands_pane = (
                f"<div class='tab-pane {'act' if tab=='commands' else ''}' data-pane='commands'>"
                f"<form method='POST' action='/save'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<div class='field'><label>Custom Command Design (/announce)</label><small>Select role to ping (or @everyone), title, accent color, and footer.</small>"
                f"<div class='row2'><div><label>Default Role to Ping</label>"
                f"<div style='display:flex;gap:8px;align-items:center'><select id='cmdRoleSelect' name='announce_role_select' style='flex:1'>{cmd_role_opts}</select>"
                f"<button type='button' class='btn btn-dark' onclick=\"tmCycleRoleSelect('cmdRoleSelect','cmdRoleStatus')\">Select Role to Ping</button></div>"
                f"<div id='cmdRoleStatus' style='color:#9ca3af;font-size:11px;margin-top:4px'>Current: {esc(sc['announce_ping'] or 'None')}</div>"
                f"<input type='text' name='announce_ping' value='{esc(sc['announce_ping'])}' placeholder='@RoleName or role ID' style='margin-top:6px'></div>"
                f"<div><label>Accent Color (Hex)</label><input type='text' name='announce_color' value='{esc(sc['announce_color'])}' placeholder='#ff7a00'></div></div>"
                f"<div class='row2' style='margin-top:10px'><div><label>Default Title</label><input type='text' name='announce_default_title' value='{esc(sc['announce_default_title'])}' placeholder='Announcement'></div>"
                f"<div><label>Custom Footer</label><input type='text' name='announce_footer' value='{esc(sc['announce_footer'])}' placeholder='TicketMint'></div></div></div>"
                f"<div class='field'><label>Commands &amp; Tools</label><small>Mod-only commands are restricted to staff/admins in <b>{esc(srv_name)}</b>; member commands are open to everyone.</small>{cmd_items}</div>"
                f"<div style='display:flex;gap:8px;flex-wrap:wrap;padding-top:14px'><button type='submit' name='act' value='save' class='btn btn-orange'>Save Command Settings &amp; Design</button></div></form>"
                f"<form method='POST' action='/save' class='field' style='margin-top:12px;border-top:1px solid #1c202b'><input type='hidden' name='server' value='{esc(sel_id)}'><input type='hidden' name='tab' value='commands'>"
                f"<label>Run Any Bot Command From Web</label><small>Pick a command, channel, and args/reason (e.g. /roll: 999; /announce: Title | Reason; /claimticket or /ticketclose: #ticket-1898 | Reason).</small>"
                f"<div class='row2'><div><label>Command</label><select name='run_cmd_name'>{run_cmd_opts}</select></div>"
                f"<div><label>Target Channel</label><select name='run_cmd_channel'>{run_ch_opts}</select></div></div>"
                f"<div style='margin-top:10px'><label>Arguments / Ticket Reason</label><input type='text' name='run_cmd_args' placeholder='Optional args or reason...'></div>"
                f"<div style='margin-top:12px'><button type='submit' name='act' value='run_cmd' class='btn btn-orange'>Run Command</button></div></form></div>"
            )

            tab_defs = [
                ("tickets", "Tickets & Roles"),
                ("welcome", "Welcome & Goodbye"),
                ("announce", "Announcements"),
                ("automod", "Auto-Mod & Limits"),
                ("verification", "Verification"),
                ("commands", "Commands & Tools"),
                ("presets", "1-Click Presets"),
            ]
            side_btns = "".join(
                f"<button type='button' data-tab='{t_key}' onclick=\"tmSwitchTab('{t_key}')\" class='tab-btn {'act' if tab==t_key else ''}'>{esc(t_lbl)}</button>"
                for t_key, t_lbl in tab_defs
            )
            side_links = (
                f"{side_btns}"
                f"<hr><form method='POST' action='/sync' style='margin:0'>"
                f"<input type='hidden' name='server' value='{esc(sel_id)}'>"
                f"<input type='hidden' name='tab' value='{esc(tab)}'>"
                f"<button type='submit' class='side-btn'>Sync Channels &amp; Roles</button></form>"
                f"<button type='button' onclick=\"window.location.href='/dashboard'\" class='side-btn'>Switch Server</button>"
            )
            html_out = (
                f"<div class='wrap'><a href='/dashboard' style='color:#9ca3af;font-size:12px'>&larr; Back to Servers</a>"
                f"<h1 style='margin:6px 0 18px;font-size:26px'>{esc(srv_name)}</h1><div class='layout'><div class='side'>{side_links}</div>"
                f"<div class='panel'>{notice}{tickets_pane}{welcome_pane}{announce_pane}{automod_pane}{verification_pane}{commands_pane}{presets_pane}</div></div></div>"
            )
            return self.send_html(page(f"{srv_name} - TicketMint", html_out, sess))

        cta = "Go to Dashboard" if sess else "Authorize & Open Dashboard"
        home = (
            f"<div class='hero'><h1>Yapin's fastest <span>ticket, mod &amp; community</span> bot.</h1>"
            f"<p>Private support tickets with transcripts, smart anti-bypass auto-mod, role ping rules, welcome cards, and an instant zero-wait dashboard.</p>"
            f"<div class='hero-btns'><a href='/dashboard' class='btn btn-orange'>{cta}</a><a href='{INVITE_URL}' class='btn btn-dark'>+ Invite Bot to Server</a></div></div>"
            f"<div class='grid'><div class='card'><h3 style='color:#ff7a00;margin-bottom:6px;font-size:16px'>Tickets &amp; Transcripts</h3><p style='color:#9ca3af;font-size:13px'>Auto-locked private rooms with claim/close buttons and automatic transcript logs.</p></div>"
            f"<div class='card'><h3 style='color:#ff7a00;margin-bottom:6px;font-size:16px'>Anti-Bypass Auto-Mod</h3><p style='color:#9ca3af;font-size:13px'>Blocks stretched words, leetspeak, protected role pings, links, caps, and spam.</p></div>"
            f"<div class='card'><h3 style='color:#ff7a00;margin-bottom:6px;font-size:16px'>Instant Web Control</h3><p style='color:#9ca3af;font-size:13px'>Instant tab switching, welcome cards, verification, announcements, and 1-click presets.</p></div></div>"
        )
        return self.send_html(page("TicketMint - Yapin' Bot", home, sess))

    def do_POST(self):
        try:
            self._handle_post()
        except Exception as e:
            self.send_html(
                page("Save Error", f"<div class='wrap'><div class='panel'><h2 style='color:#ff7a00'>Action Failed</h2><p style='color:#9ca3af;margin-top:8px'>{esc(clean_err(e))}</p><div style='margin-top:14px'><a href='/dashboard' class='btn btn-orange'>Back to Dashboard</a></div></div></div>")
            )

    def _handle_post(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length).decode("utf-8", errors="ignore")
        data = urllib.parse.parse_qs(raw_body)
        sess = self.get_sess()
        u = urllib.parse.urlsplit(self.path)
        path = u.path
        sid = data.get("server", [""])[0].strip()
        tab = data.get("tab", ["tickets"])[0].strip().lower()
        if tab not in ("tickets", "welcome", "announce", "automod", "verification", "commands", "presets"):
            tab = "tickets"
        act = data.get("act", ["save"])[0].strip().lower()

        if sess and sid and path == "/sync":
            existing_meta = {}
            try:
                mraw = r_cmd("GET", f"ticketmint:meta:{sid}")
                if mraw:
                    parsed_m = json.loads(mraw)
                    if isinstance(parsed_m, dict):
                        existing_meta = parsed_m
            except Exception:
                pass
            sync_server_metadata(sid, existing_meta)
            queue_outbox({"type": "sync_meta", "server_id": sid})
            return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab={urllib.parse.quote(tab)}&synced=1")

        if sess and sid:
            all_cfg = load_all_cfg()
            cur = get_scfg(sid)
            if tab == "tickets":
                cur["roles"] = data.get("roles", [])
                cur["allowed_ping_roles"] = data.get("allowed_ping_roles", [])
                cur["protected_ping_roles"] = data.get("protected_ping_roles", [])
                cur["block_unpingable_roles"] = bool(data.get("block_unpingable_roles"))
                cur["warn_role_ping_msg"] = data.get("warn_role_ping_msg", ["{user}, you cannot ping protected roles."])[0].strip() or "{user}, you cannot ping protected roles."
                cur["dash"] = data.get("dash", [""])[0].strip()
                cur["cat"] = data.get("cat", [""])[0].strip()
                cur["logs"] = data.get("logs", [""])[0].strip()
                cur["ticket_open_msg"] = data.get("ticket_open_msg", [DEFAULT_OPEN_MSG])[0].strip() or DEFAULT_OPEN_MSG
                cur["ticket_close_msg"] = data.get("ticket_close_msg", [DEFAULT_CLOSE_MSG])[0].strip() or DEFAULT_CLOSE_MSG
                t_reason = data.get("ticket_test_reason", ["No reason provided"])[0].strip() or "No reason provided"
                all_cfg[sid] = cur
                save_all_cfg(all_cfg, sid)
                if act == "post":
                    ok, err = post_panel(cur["dash"], sid=sid)
                    if not ok:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&err={urllib.parse.quote(err)}")
                    return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&sent=1")
                if act == "modping":
                    ok, err = send_msg_smart(cur["dash"], content=f"Staff check-in triggered by @{sess['username']} • TicketMint", kind="modping", extra={"server_id": sid})
                    if not ok:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&err={urllib.parse.quote(err)}")
                    return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&sent=1")
                if act in ("test_ticket_open", "test_ticket_close"):
                    log_ch = cur["logs"] or cur["dash"]
                    if not log_ch:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&err={urllib.parse.quote('Select a Ticket Logs or Panel Channel first.')}")
                    sname = resolve_server_name(sid)
                    ev = "open" if act == "test_ticket_open" else "close"
                    tpl = cur["ticket_open_msg"] if ev == "open" else cur["ticket_close_msg"]
                    formatted = format_ticket_log_message(tpl, f"@{sess['username']}", "#ticket-1898", reason=t_reason, server_name=sname, claimer=f"@{sess['username']}")
                    ok, err = send_msg_smart(
                        log_ch,
                        title="🎫 Ticket Opened" if ev == "open" else "🔒 Ticket Closed",
                        description=f"{formatted}\n**Reason:** {t_reason}",
                        color_hex="#22c55e" if ev == "open" else "#ef4444",
                        footer=f"TicketMint • {sname}",
                        kind="ticket_log",
                        extra={"server_id": sid, "event": ev, "user": f"@{sess['username']}", "ticket": "#ticket-1898", "reason": t_reason, "server_name": sname},
                    )
                    if not ok:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&err={urllib.parse.quote(err)}")
                    return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&sent=1")
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=tickets&saved=1")
            if tab == "welcome":
                cur["welcome"] = data.get("welcome", [""])[0].strip()
                cur["autorole"] = data.get("autorole", [""])[0].strip()
                cur["w_title"] = data.get("w_title", ["Welcome!"])[0].strip() or "Welcome!"
                cur["w_msg"] = data.get("w_msg", ["Welcome {user} to {server}! You are our {ordinal} member!"])[0].strip() or "Welcome {user} to {server}! You are our {ordinal} member!"
                cur["w_banner"] = data.get("w_banner", [""])[0].strip()
                cur["w_card"] = bool(data.get("w_card"))
                w_col = data.get("w_color", ["#ff7a00"])[0].strip()
                cur["w_color"] = w_col if re.match(r"^#[0-9a-fA-F]{6}$", w_col) else "#ff7a00"
                cur["goodbye"] = data.get("goodbye", [""])[0].strip()
                cur["g_msg"] = data.get("g_msg", ["{user} just left {server}. We now have {member_count} members."])[0].strip() or "{user} just left {server}. We now have {member_count} members."
                all_cfg[sid] = cur
                save_all_cfg(all_cfg, sid)
                if act == "test_welcome":
                    target_ch = cur["welcome"] or cur["dash"]
                    if not target_ch:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=welcome&err={urllib.parse.quote('Select a Welcome Channel first.')}")
                    fetched = u_dict(safe_y("GET", f"/servers/{sid}"), "server")
                    sname = resolve_server_name(sid, fetched=fetched)
                    m_cnt = (fetched.get("member_count") if isinstance(fetched, dict) else None) or len(u_list(safe_y("GET", f"/servers/{sid}/members"), "members")) or 5
                    ping_str = f"<@{sess['id']}>"
                    txt = (
                        cur["w_msg"]
                        .replace("{user}", ping_str)
                        .replace("{server}", sname)
                        .replace("{member_count}", str(m_cnt))
                        .replace("{ordinal}", ordinal_num(m_cnt))
                    )
                    ok, err = send_msg_smart(
                        target_ch,
                        ping=ping_str,
                        title=cur["w_title"],
                        description=txt,
                        color_hex=cur["w_color"],
                        image_url=cur["w_banner"],
                        footer=f"Member #{m_cnt} • Test Welcome Card",
                        kind="welcome_test",
                        extra={"server_id": sid, "server_name": sname, "member_count": m_cnt},
                    )
                    if not ok:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=welcome&err={urllib.parse.quote(err)}")
                    return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=welcome&sent=1")
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=welcome&saved=1")
            if tab == "announce":
                ann_cid = data.get("ann_channel", [""])[0].strip()
                ann_title = data.get("ann_title", [cur["announce_default_title"]])[0].strip() or cur["announce_default_title"] or "Announcement"
                ann_body = data.get("ann_body", [""])[0].strip()
                custom_ping = data.get("ann_custom_ping", [""])[0].strip()
                role_sel_ping = data.get("ann_role_select", [""])[0].strip()
                chosen_ping = custom_ping or role_sel_ping or cur["announce_ping"]
                ping = "@everyone" if data.get("ann_everyone") else chosen_ping
                if not ann_cid or not ann_body:
                    return self.redir(
                        f"/dashboard?server={urllib.parse.quote(sid)}&tab=announce&err={urllib.parse.quote('Choose a channel and enter a message.')}"
                    )
                ok, err = send_msg_smart(
                    ann_cid,
                    ping=ping,
                    title=ann_title,
                    description=ann_body,
                    color_hex=cur["announce_color"] or "#ff7a00",
                    footer=cur["announce_footer"] or f"Announced by @{sess['username']} • TicketMint",
                    kind="announce",
                    extra={"server_id": sid},
                )
                if not ok:
                    return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=announce&err={urllib.parse.quote(err)}")
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=announce&sent=1")
            if tab == "automod":
                cur["anti_link"] = bool(data.get("anti_link"))
                cur["anti_caps"] = bool(data.get("anti_caps"))
                cur["word_filter"] = bool(data.get("word_filter"))
                cur["anti_spam"] = bool(data.get("anti_spam"))
                try:
                    cur["max_tickets"] = max(1, min(10, int(data.get("max_tickets", ["2"])[0] or 2)))
                except Exception:
                    cur["max_tickets"] = 2
                try:
                    cur["ticket_cooldown"] = max(0, min(3600, int(data.get("ticket_cooldown", ["30"])[0] or 0)))
                except Exception:
                    cur["ticket_cooldown"] = 30
                cur["blocked_words"] = data.get("blocked_words", [""])[0].strip()
                cur["warn_word_msg"] = data.get("warn_word_msg", ["{user}, that word is not allowed here."])[0].strip() or "{user}, that word is not allowed here."
                cur["warn_link_msg"] = data.get("warn_link_msg", ["{user}, links are not allowed in this channel."])[0].strip() or "{user}, links are not allowed in this channel."
                all_cfg[sid] = cur
                save_all_cfg(all_cfg, sid)
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=automod&saved=1")
            if tab == "verification":
                cur["verify_role"] = data.get("verify_role", [""])[0].strip()
                cur["verify_channel"] = data.get("verify_channel", [""])[0].strip()
                all_cfg[sid] = cur
                save_all_cfg(all_cfg, sid)
                if act == "post_verify":
                    if not cur["verify_channel"]:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=verification&err={urllib.parse.quote('Select a Verification Channel first.')}")
                    fetched = u_dict(safe_y("GET", f"/servers/{sid}"), "server")
                    sname = resolve_server_name(sid, fetched=fetched)
                    ok, err = post_verify_panel(cur["verify_channel"], sname, sid=sid)
                    if not ok:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=verification&err={urllib.parse.quote(err)}")
                    return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=verification&sent=1")
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=verification&saved=1")
            if tab == "presets":
                if act == "preset_gaming":
                    cur.update({"anti_link": True, "word_filter": True, "anti_spam": True, "max_tickets": 2, "ticket_cooldown": 30, "w_card": True, "active_preset": "preset_gaming"})
                elif act == "preset_strict":
                    cur.update({"anti_link": True, "anti_caps": True, "word_filter": True, "anti_spam": True, "max_tickets": 1, "ticket_cooldown": 60, "active_preset": "preset_strict"})
                elif act == "preset_chill":
                    cur.update({"anti_link": False, "anti_caps": False, "word_filter": True, "anti_spam": True, "max_tickets": 3, "ticket_cooldown": 15, "active_preset": "preset_chill"})
                all_cfg[sid] = cur
                save_all_cfg(all_cfg, sid)
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=presets&saved=1")
            if tab == "commands":
                if act == "run_cmd":
                    rc_name = data.get("run_cmd_name", [""])[0].strip().lower()
                    rc_ch = data.get("run_cmd_channel", [""])[0].strip() or cur["dash"]
                    rc_args = data.get("run_cmd_args", [""])[0].strip()
                    if not rc_name:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&err={urllib.parse.quote('Pick a command to run.')}")
                    if rc_name == "ticketpanel":
                        ok, err = post_panel(rc_ch, sid=sid)
                        if not ok:
                            return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&err={urllib.parse.quote(err)}")
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&sent=1")
                    if rc_name == "verifypanel":
                        sname = resolve_server_name(sid)
                        ok, err = post_verify_panel(rc_ch, sname, sid=sid)
                        if not ok:
                            return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&err={urllib.parse.quote(err)}")
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&sent=1")
                    if rc_name == "announce":
                        title, sep, body = rc_args.partition("|")
                        if sep:
                            ann_t = title.strip() or cur["announce_default_title"] or "Announcement"
                            ann_b = body.strip() or "No reason provided"
                        else:
                            ann_t = cur["announce_default_title"] or "Announcement"
                            ann_b = rc_args or "No reason provided"
                        ok, err = send_msg_smart(
                            rc_ch,
                            ping=cur["announce_ping"],
                            title=ann_t,
                            description=ann_b,
                            color_hex=cur["announce_color"] or "#ff7a00",
                            footer=cur["announce_footer"] or f"Announced by @{sess['username']} • TicketMint",
                            kind="announce",
                            extra={"server_id": sid},
                        )
                        if not ok:
                            return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&err={urllib.parse.quote(err)}")
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&sent=1")
                    if rc_name == "roll":
                        upper = 999
                        if rc_args.isdigit():
                            upper = max(2, min(999, int(rc_args)))
                        rolled = random.randint(1, upper)
                        ok, err = send_msg_smart(
                            rc_ch,
                            content=f"🎲 <@{sess['id']}> rolled **{rolled}** (1–{upper})!",
                            kind="send_message",
                            extra={"server_id": sid},
                        )
                        if not ok:
                            return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&err={urllib.parse.quote(err)}")
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&sent=1")
                    ok = queue_outbox({
                        "type": "run_command",
                        "command": rc_name,
                        "server_id": sid,
                        "channel_id": rc_ch,
                        "args": rc_args,
                        "user_id": sess["id"],
                        "username": sess["username"],
                    })
                    if not ok:
                        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&err={urllib.parse.quote('Could not queue command.')}")
                    return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&sent=1")

                enabled = set(data.get("enabled_cmds", []))
                cur["disabled_cmds"] = [k for k, _, _, _ in ALL_COMMANDS if k not in enabled]
                typed_ping = data.get("announce_ping", [""])[0].strip()
                picked_ping = data.get("announce_role_select", [""])[0].strip()
                cur["announce_ping"] = typed_ping or picked_ping
                w_col = data.get("announce_color", ["#ff7a00"])[0].strip()
                cur["announce_color"] = w_col if re.match(r"^#[0-9a-fA-F]{6}$", w_col) else "#ff7a00"
                cur["announce_default_title"] = data.get("announce_default_title", ["Announcement"])[0].strip() or "Announcement"
                cur["announce_footer"] = data.get("announce_footer", [""])[0].strip()
                all_cfg[sid] = cur
                save_all_cfg(all_cfg, sid)
                return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&tab=commands&saved=1")
        return self.redir(f"/dashboard?server={urllib.parse.quote(sid)}&saved=1")
