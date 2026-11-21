import datetime, io, json, os, re, struct, tempfile, threading, time, urllib.request, zlib
from yapper import Bot, row, btn

BOT_TOKEN = "yb_23404489.PlvFt0GgzYy6Z-SGp8ZHfSvOh0io7LhVL7KggSTY"
REDIS_URL = "https://" + "profound-seasnail-108379.upstash.io"
REDIS_TOKEN = "gQAAAAAAAadbAAIgcDI4MTE2MjY4ODFkZGM0ZmQ1Yjg0NGE5MmU5YTAwYTI3Nw"
SITE_URL = "https://" + "ticketmint-web.vercel.app"
AV_CDN = "https://" + "files.yapper.website/avatars/"

bot = Bot(token=BOT_TOKEN)
OPEN_COOLDOWN = {}
BOT_SELF_ID = ""
USER_AV_CACHE = {}

def r_cmd(*args):
    if not REDIS_TOKEN:
        return None
    req = urllib.request.Request(
        REDIS_URL,
        data=json.dumps(list(args)).encode("utf-8"),
        headers={"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8")).get("result")

def u_list(d, k):
    return d if isinstance(d, list) else (d.get(k, []) if isinstance(d, dict) else [])

def u_dict(d, k):
    return d.get(k, d) if isinstance(d, dict) else {}

def load_all_cfg():
    try:
        raw = r_cmd("GET", "ticketmint:cfg")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}

def save_all_cfg(d):
    try:
        r_cmd("SET", "ticketmint:cfg", json.dumps(d))
    except Exception as e:
        print("[Config Save Note]:", e)
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

def is_cmd_disabled(sid, cmd_key):
    if not sid:
        return False
    return cmd_key in set(get_scfg(sid).get("disabled_cmds", []))

def cmd_text(ctx):
    a = str(getattr(ctx, "args", "") or "").strip()
    if a:
        return a
    opts = getattr(ctx, "options", None)
    if isinstance(opts, dict) and opts:
        return " ".join(str(v) for v in opts.values() if v is not None).strip()
    c = str(getattr(ctx, "content", "") or "").strip()
    return c.partition(" ")[-1].strip() if " " in c else ""

def format_msg_date(obj=None):
    raw_ts = None
    if isinstance(obj, dict):
        raw_ts = obj.get("created_at") or obj.get("timestamp")
    elif obj is not None:
        raw_ts = getattr(obj, "created_at", None) or getattr(obj, "timestamp", None)
    if raw_ts:
        try:
            s = str(raw_ts).replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(s)
            return dt.strftime("%b %d, %Y")
        except Exception:
            pass
    return datetime.datetime.now().strftime("%b %d, %Y")

def extract_modal_pair(i, k1, k2):
    sources = []
    for attr in ("values", "fields", "inputs", "data", "_data", "raw"):
        val = getattr(i, attr, None)
        if val is not None:
            sources.append(val)
    try:
        sources.append(vars(i))
    except Exception:
        pass
    v1, v2 = "", ""
    def walk(obj):
        nonlocal v1, v2
        if isinstance(obj, dict):
            if k1 in obj and obj[k1] and not v1:
                v1 = str(obj[k1])
            if k2 in obj and obj[k2] and not v2:
                v2 = str(obj[k2])
            cid = obj.get("custom_id") or obj.get("id") or obj.get("name")
            val = obj.get("value") if obj.get("value") is not None else obj.get("text")
            if cid == k1 and val and not v1:
                v1 = str(val)
            elif cid == k2 and val and not v2:
                v2 = str(val)
            for v in obj.values():
                if isinstance(v, (dict, list, tuple)):
                    walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item)
    for src in sources:
        walk(src)
    return v1.strip(), v2.strip()
    def get_uname(obj, fallback="User"):
    if obj is None:
        return fallback
    if isinstance(obj, dict):
        for k in ("display_name", "username", "global_name", "name", "nick"):
            if obj.get(k):
                return str(obj[k])
        if isinstance(obj.get("user"), dict):
            return get_uname(obj["user"], fallback)
        return fallback
    for attr in ("display_name", "username", "global_name", "name", "nick"):
        v = getattr(obj, attr, None)
        if v:
            return str(v)
    return fallback

def scan_url(obj, depth=0):
    if obj is None or depth > 4:
        return ""
    if isinstance(obj, str):
        return obj if obj.startswith("http") else ""
    if isinstance(obj, dict):
        av_url = obj.get("avatar_url")
        if isinstance(av_url, str) and av_url.startswith("http"):
            return av_url
        av_path = obj.get("avatar_path")
        if isinstance(av_path, str) and av_path:
            return av_path if av_path.startswith("http") else f"{AV_CDN}{av_path.lstrip('/')}"
        for k in ("avatar", "photo_url", "photo", "pfp", "image_url", "image"):
            v = obj.get(k)
            if isinstance(v, str) and v:
                if v.startswith("http"):
                    return v
                if "/" in v:
                    return f"{AV_CDN}{v.lstrip('/')}"
        for k, v in obj.items():
            if "banner" in str(k).lower():
                continue
            found = scan_url(v, depth + 1)
            if found:
                return found
        return ""
    if isinstance(obj, (list, tuple)):
        for item in obj:
            found = scan_url(item, depth + 1)
            if found:
                return found
        return ""
    for attr in ("avatar_url", "avatar_path", "avatar", "data", "_data", "raw", "user"):
        try:
            val = getattr(obj, attr, None)
            if attr == "avatar_path" and isinstance(val, str) and val:
                return val if val.startswith("http") else f"{AV_CDN}{val.lstrip('/')}"
            found = scan_url(val, depth + 1)
            if found:
                return found
        except Exception:
            pass
    try:
        return scan_url(vars(obj), depth + 1)
    except Exception:
        return ""

def cache_user_obj(u):
    if u is None:
        return
    uid = u.get("id") if isinstance(u, dict) else getattr(u, "id", None)
    av = scan_url(u)
    if uid and av:
        USER_AV_CACHE[str(uid)] = av
        def clean_mentions(txt, sid):
    if not txt or "<@" not in txt:
        return txt
    names = {}
    if sid:
        for m in u_list(bot.api("GET", f"/servers/{sid}/members"), "members"):
            u = m.get("user") if isinstance(m.get("user"), dict) else m
            if u.get("id"):
                names[str(u["id"])] = get_uname(u, "User")
    def repl(match):
        mid = match.group(1)
        return f"@{names.get(mid, 'User')}"
    return re.sub(r"<@!?([a-zA-Z0-9-]+)>", repl, txt)

def sync_web_meta():
    global BOT_SELF_ID
    try:
        me_raw = bot.api("GET", "/me")
        me_bot = u_dict(me_raw, "bot")
        BOT_SELF_ID = str(me_bot.get("id") or me_raw.get("id") or BOT_SELF_ID)
        srvs = u_list(me_raw, "servers") or u_list(bot.api("GET", "/servers"), "servers")
        known_ids = {s.get("id") for s in srvs if s.get("id")}
        for cfg_id in load_all_cfg().keys():
            if cfg_id and cfg_id not in known_ids:
                srvs.append({"id": cfg_id})
        if srvs:
            out = []
            for s in srvs:
                sid = s.get("id")
                if not sid:
                    continue
                full = u_dict(bot.api("GET", f"/servers/{sid}"), "server")
                if not full or not full.get("id"):
                    full = s
                m_cnt = full.get("member_count") or s.get("member_count") or len(u_list(bot.api("GET", f"/servers/{sid}/members"), "members"))
                out.append({
                    "id": sid,
                    "name": full.get("name") or s.get("name") or f"Server ({sid})",
                    "owner_id": full.get("owner_id") or s.get("owner_id") or "",
                    "icon": full.get("icon_url") or full.get("icon") or s.get("icon") or "",
                    "member_count": m_cnt,
                })
                roles = u_list(bot.api("GET", f"/servers/{sid}/roles"), "roles")
                chs = u_list(bot.api("GET", f"/servers/{sid}/channels"), "channels")
                r_cmd("SET", f"ticketmint:meta:{sid}", json.dumps({"roles": roles, "channels": chs}))
            r_cmd("SET", "ticketmint:servers", json.dumps(out))
            print(f"[WebSync] Synced {len(out)} server(s) to {SITE_URL}!")
    except Exception as e:
        print("[WebSync] Note:", e)

def is_staff(sid, uid):
    try:
        sc = get_scfg(sid)
        srv = u_dict(bot.api("GET", f"/servers/{sid}"), "server")
        if str(srv.get("owner_id", "")) == str(uid):
            return True
        mem = u_dict(bot.api("GET", f"/servers/{sid}/members/{uid}"), "member")
        mroles = set(mem.get("roles", []))
        if any(r in mroles for r in sc["roles"]):
            return True
        for r in u_list(bot.api("GET", f"/servers/{sid}/roles"), "roles"):
            if r.get("id") in mroles:
                p = r.get("permissions", {})
                if isinstance(p, dict) and (p.get("administrator") or p.get("manage_server") or p.get("manage_channels")):
                    return True
    except Exception:
        return True
    return False
    def resolve_user(sid, raw_target, fallback_id, fallback_name, ctx_obj=None):
    cache_user_obj(ctx_obj)
    if ctx_obj is not None:
        cache_user_obj(getattr(ctx_obj, "author", None))
    uid = re.sub(r"[<@!>]", "", str(raw_target or "")).strip()
    target_id = uid or str(fallback_id)
    found_name = str(fallback_name or "User")
    found_av = USER_AV_CACHE.get(target_id, "") or (scan_url(ctx_obj) if not uid else "")
    if sid:
        members = u_list(bot.api("GET", f"/servers/{sid}/members"), "members")
        for m in members:
            cache_user_obj(m)
            u = m.get("user") if isinstance(m.get("user"), dict) else m
            uname = str(u.get("username") or "")
            dname = get_uname(u, "")
            mid = str(u.get("id") or m.get("user_id") or m.get("id") or "")
            if (uid and (mid == uid or uname.lower() == uid.lower() or dname.lower() == uid.lower())) or (not uid and mid == str(fallback_id)):
                target_id = mid or target_id
                found_name = dname or uname or found_name
                found_av = scan_url(m) or USER_AV_CACHE.get(target_id, "") or found_av
                break
        if not found_av and target_id:
            mem = bot.api("GET", f"/servers/{sid}/members/{target_id}")
            cache_user_obj(mem)
            found_av = scan_url(mem) or USER_AV_CACHE.get(target_id, "")
            found_name = get_uname(u_dict(mem, "member"), found_name)
    if not found_av and target_id:
        for ep in (f"/users/{target_id}", f"/user/{target_id}"):
            u_res = bot.api("GET", ep)
            cache_user_obj(u_res)
            found_av = scan_url(u_res)
            if found_av:
                found_name = get_uname(u_dict(u_res, "user"), found_name)
                break
    return target_id, found_name, found_av

def load_font(size, bold=True):
    from PIL import ImageFont
    win_fonts = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "verdanab.ttf"] if bold else ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
    for fn in win_fonts:
        p = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", fn)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()
        def build_quote_png(quote_text, author_name, avatar_url="", date_str=""):
    W, H = 1000, 440
    date_label = date_str or datetime.datetime.now().strftime("%b %d, %Y")
    try:
        from PIL import Image, ImageDraw
        card = Image.new("RGBA", (W, H), (11, 13, 18, 255))
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle((16, 16, W - 16, H - 16), radius=28, fill=(20, 24, 34, 255), outline=(255, 122, 0, 255), width=3)
        draw.rounded_rectangle((36, 44, 46, H - 44), radius=5, fill=(255, 122, 0, 255))
        av_size = 190
        av_x, av_y = 78, (H - av_size) // 2
        draw.ellipse((av_x - 6, av_y - 6, av_x + av_size + 6, av_y + av_size + 6), fill=(255, 122, 0, 255))
        av_img = None
        if avatar_url and str(avatar_url).startswith("http"):
            try:
                req = urllib.request.Request(avatar_url, headers={"User-Agent": "TicketMint/1.0"})
                av_bytes = urllib.request.urlopen(req, timeout=6).read()
                av_img = Image.open(io.BytesIO(av_bytes)).convert("RGBA").resize((av_size, av_size))
            except Exception:
                av_img = None
        if av_img is None:
            av_img = Image.new("RGBA", (av_size, av_size), (32, 38, 54, 255))
            d_av = ImageDraw.Draw(av_img)
            f_init = load_font(88, True)
            d_av.text((62, 42), (author_name[:1] or "T").upper(), fill=(255, 122, 0, 255), font=f_init)
        mask = Image.new("L", (av_size, av_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
        card.paste(av_img, (av_x, av_y), mask)

        txt = str(quote_text).strip()
        f_size = 40 if len(txt) <= 55 else (32 if len(txt) <= 115 else 25)
        max_chars = 26 if f_size == 40 else (33 if f_size == 32 else 42)
        f_quote = load_font(f_size, True)
        f_big_q = load_font(76, True)
        f_author = load_font(25, True)
        f_date = load_font(19, False)
        f_tag = load_font(18, False)
        words = txt.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) + 1 <= max_chars:
                cur = f"{cur} {w}".strip()
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        lines = lines[:5]
        tx = 315
        draw.text((tx, 36), "“", fill=(255, 122, 0, 255), font=f_big_q)
        line_h = f_size + 14
        start_y = max(100, (H - len(lines) * line_h) // 2 - 22)
        for idx, ln in enumerate(lines):
            draw.text((tx + 8, start_y + idx * line_h), ln, fill=(248, 250, 252, 255), font=f_quote)
        draw.line([(tx + 8, H - 102), (tx + 72, H - 102)], fill=(255, 122, 0, 255), width=4)
        draw.text((tx + 8, H - 90), f"@{author_name}", fill=(255, 255, 255, 255), font=f_author)
        draw.text((tx + 8, H - 56), date_label, fill=(148, 163, 184, 255), font=f_date)
        draw.text((W - 140, H - 48), "TicketMint", fill=(148, 163, 184, 255), font=f_tag)
        buf = io.BytesIO()
        card.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        raw = bytearray()
        for y in range(H):
            row_b = bytearray(b"\x00")
            for x in range(W):
                row_b.extend(b"\xff\x7a\x00\xff" if x < 10 else b"\x0b\x0d\x12\xff")
            raw.extend(row_b)
        def mk_chunk(tag, d):
            return struct.pack(">I", len(d)) + tag + d + struct.pack(">I", zlib.crc32(tag + d) & 0xFFFFFFFF)
        return b"\x89PNG\r\n\x1a\n" + mk_chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)) + mk_chunk(b"IDAT", zlib.compress(bytes(raw))) + mk_chunk(b"IEND", b"")

def send_quote_with_cleanup(quote_text, author_name, avatar_url="", date_str="", channel_id=None, reply_to=None):
    png = build_quote_png(quote_text, author_name, avatar_url, date_str)
    fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="tm_quote_")
    os.close(fd)
    try:
        with open(tmp_path, "wb") as f:
            f.write(png)
        bot.send(channel_id, content="", reply_to=reply_to, files=[tmp_path])
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
            def send_ticket_panel(cid):
    bname = u_dict(bot.api("GET", "/me"), "bot").get("name", "TicketMint")
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
    bot.api("POST", f"/channels/{cid}/messages", payload)

def close_ticket_now(sid, cid, uid, reason="No reason provided"):
    sc = get_scfg(sid)
    if sc["logs"]:
        try:
            bot.api("POST", f"/channels/{sc['logs']}/messages", {"embeds": [{"title": "Ticket Closed", "description": f"Channel <#{cid}> closed by <@{uid}>.\n**Reason:** {reason}", "color": 0xFF7A00}]})
        except Exception:
            pass
    time.sleep(3)
    bot.api("DELETE", f"/channels/{cid}")

def bg_sync_loop():
    while True:
        time.sleep(30)
        sync_web_meta()

@bot.on("ready")
def on_ready(data):
    print("TicketMint is online!")
    sync_web_meta()
    threading.Thread(target=bg_sync_loop, daemon=True).start()

@bot.on("server_create")
def on_server_join(data):
    sync_web_meta()

@bot.command(name="help", description="View all TicketMint commands and dashboard link")
def help_cmd(ctx):
    em = {
        "title": "TicketMint — Command Guide",
        "description": (
            "**Ticket System**\n"
            "• `/ticketpanel` — Post the orange Open a Ticket panel\n"
            "• `/modroles` — Add, remove, or view staff roles\n"
            "• `/claimticket` — Claim the current open ticket\n"
            "• `/ticketclose` — Close and log the current ticket\n\n"
            "**Server & Fun Tools**\n"
            "• `/announce Title | Message` — Post a styled announcement (add `| everyone` to ping)\n"
            "• `/pfp [@user]` — View any member's full-size profile picture\n"
            "• `/makeitquote` — Turn text (or a reply + `@TicketMint` ping) into a dated quote card\n"
            "• `/setwelcomechannel` — Set the Welcome channel\n"
            "• `/dashboard` — Open the 24/7 web dashboard\n\n"
            f"**Web Dashboard:** {SITE_URL}/dashboard"
        ),
        "color": 0xFF7A00,
    }
    ctx.reply(embeds=[em])

@bot.command(name="dashboard", description="Get the link to configure TicketMint on the web")
def dash_cmd(ctx):
    sync_web_meta()
    ctx.reply(f"Configure **TicketMint** anytime at: {SITE_URL}/dashboard")
    @bot.command(name="announce", description="Post a styled announcement: /announce Title | Message (add | everyone to ping)")
def announce_cmd(ctx):
    sid = getattr(ctx, "server_id", "")
    if is_cmd_disabled(sid, "announce"):
        return ctx.ephemeral("`/announce` is disabled on the web dashboard for this server.")
    uid = getattr(ctx, "user_id", "") or getattr(ctx, "author_id", "")
    if not is_staff(sid, uid):
        return ctx.ephemeral("Only staff members can send announcements.")
    raw = cmd_text(ctx)
    if not raw:
        return ctx.ephemeral("Type `/announce Title | Your message` (example: `/announce HEYYYY GUYS | IM THE BEST GUYS`)")
    if "|" in raw:
        left, _, right = raw.partition("|")
        title = left.strip() or "Announcement"
        body = right.strip()
        ping_txt = ""
        if body.lower().endswith("| everyone"):
            body = body[:-10].strip()
            ping_txt = "@everyone"
        elif body.lower().endswith("|everyone"):
            body = body[:-9].strip()
            ping_txt = "@everyone"
    else:
        title = "Announcement"
        body = raw.strip()
        ping_txt = ""
    if not body:
        return ctx.ephemeral("Please add your message after `|`, e.g. `/announce HEYYYY GUYS | IM THE BEST GUYS`")
    _, staff_name, _ = resolve_user(sid, uid, uid, get_uname(getattr(ctx, "author", None), "Staff"), ctx)
    bot.api("POST", f"/channels/{ctx.channel_id}/messages", {
        "content": ping_txt,
        "embeds": [{
            "description": f"## {title}\n\n{body}",
            "color": 0xFF7A00,
            "footer": {"text": f"Announced by @{staff_name} • TicketMint"},
        }],
    })
    ctx.ephemeral("Announcement posted!")

@bot.command(name="pfp", description="Show the profile picture of a user", options=[
    {"name": "user", "description": "Member to view (leave empty for yourself)", "type": "string", "required": False},
])
def pfp_cmd(ctx):
    sid = getattr(ctx, "server_id", "")
    if is_cmd_disabled(sid, "pfp"):
        return ctx.ephemeral("`/pfp` is disabled on the web dashboard for this server.")
    uid0 = getattr(ctx, "user_id", "") or getattr(ctx, "author_id", "")
    opts = getattr(ctx, "options", None) or {}
    target = str(opts.get("user") or "").strip() if isinstance(opts, dict) and opts.get("user") else cmd_text(ctx)
    author_name = get_uname(getattr(ctx, "author", None), "User")
    uid, uname, av = resolve_user(sid, target, uid0, author_name, ctx)
    if not av:
        return ctx.reply(f"**{uname}** does not have a custom profile picture set.")
    em = {"title": f"{uname}'s Profile Picture", "image": {"url": av}, "color": 0xFF7A00}
    ctx.reply(embeds=[em])

@bot.command(name="makeitquote", description="Create a quote card image from text", options=[
    {"name": "text", "description": "The quote text to put on the card", "type": "string", "required": True},
])
def makeitquote_cmd(ctx):
    sid = getattr(ctx, "server_id", "")
    if is_cmd_disabled(sid, "makeitquote"):
        return ctx.ephemeral("`/makeitquote` is disabled on the web dashboard for this server.")
    uid0 = getattr(ctx, "user_id", "") or getattr(ctx, "author_id", "")
    opts = getattr(ctx, "options", None) or {}
    raw_q = str(opts.get("text") or "").strip() if isinstance(opts, dict) and opts.get("text") else cmd_text(ctx)
    q = clean_mentions(raw_q, sid)
    if not q:
        return ctx.ephemeral("Please enter text to quote!")
    author_name = get_uname(getattr(ctx, "author", None), "User")
    uid, uname, av = resolve_user(sid, "", uid0, author_name, ctx)
    ctx.ephemeral("Creating your quote card...")
    send_quote_with_cleanup(q[:220], uname, av, format_msg_date(ctx), channel_id=ctx.channel_id)
    @bot.on("message")
def on_message_quote(msg):
    try:
        cache_user_obj(msg)
        author = getattr(msg, "author", None)
        cache_user_obj(author)
        is_bot = author.get("bot", False) if isinstance(author, dict) else getattr(author, "bot", False)
        if is_bot:
            return
        sid = str(getattr(msg, "server_id", "") or "")
        if is_cmd_disabled(sid, "replyquote"):
            return
        content = str(getattr(msg, "content", "") or "")
        if not ((BOT_SELF_ID and BOT_SELF_ID in content) or ("ticketmint" in content.lower())):
            return
        cid = str(getattr(msg, "channel_id", "") or "")
        ref = getattr(msg, "referenced_message", None) or getattr(msg, "reply_to", None)
        ref_id = getattr(msg, "reply_to_id", None) or getattr(msg, "referenced_message_id", None)
        if isinstance(ref, str):
            ref_id = ref
            ref = None
        if ref is None and ref_id and cid:
            ref = u_dict(bot.api("GET", f"/channels/{cid}/messages/{ref_id}"), "message")
        if not ref:
            return
        cache_user_obj(ref)
        q_author = getattr(ref, "author", None) if not isinstance(ref, dict) else ref.get("author")
        cache_user_obj(q_author)
        q_uid = str((q_author.get("id") if isinstance(q_author, dict) else getattr(q_author, "id", "")) or "")
        if not q_uid:
            q_uid = str((ref.get("author_id") if isinstance(ref, dict) else getattr(ref, "author_id", "")) or "")
        q_name = get_uname(q_author, "Member")
        q_av = scan_url(q_author) or USER_AV_CACHE.get(q_uid, "")
        if (not q_av or q_name == "Member") and q_uid:
            _, q_name, q_av = resolve_user(sid, q_uid, q_uid, q_name, q_author)
        raw_q = str(getattr(ref, "content", None) if not isinstance(ref, dict) else ref.get("content") or "").strip()
        q_txt = clean_mentions(raw_q, sid)
        if q_txt and cid:
            send_quote_with_cleanup(q_txt[:220], q_name, q_av, format_msg_date(ref), channel_id=cid, reply_to=getattr(msg, "id", None))
    except Exception as e:
        print("[ReplyQuote Note]:", e)

def handle_welcome_event(data, is_join=True):
    try:
        if not isinstance(data, dict):
            return
        sid = data.get("server_id") or data.get("guild_id")
        if not sid:
            return
        sc = get_scfg(sid)
        user = data.get("user") or (data.get("member") or {}).get("user") or data
        uid = user.get("id")
        uname = user.get("username") or user.get("name") or "Member"
        srv = u_dict(bot.api("GET", f"/servers/{sid}"), "server")
        sname = srv.get("name") or "the server"
        if is_join and sc["welcome"]:
            txt = sc["w_msg"].replace("{user}", f"<@{uid}>" if uid else uname).replace("{server}", sname)
            col = int(sc["w_color"].lstrip("#"), 16) if str(sc["w_color"]).startswith("#") else 0xFF7A00
            em = {"title": sc["w_title"] or "Welcome!", "description": txt, "color": col}
            if sc["w_banner"]:
                em["image"] = {"url": sc["w_banner"]}
            bot.api("POST", f"/channels/{sc['welcome']}/messages", {"embeds": [em]})
        elif not is_join and sc["goodbye"]:
            txt = sc["g_msg"].replace("{user}", f"**{uname}**").replace("{server}", sname)
            bot.api("POST", f"/channels/{sc['goodbye']}/messages", {"embeds": [{"title": "Goodbye", "description": txt, "color": 0xFF7A00}]})
    except Exception as e:
        print("[Welcome Event Note]:", e)

for ev_j in ("member_join", "server_member_add", "guild_member_add"):
    bot.on(ev_j)(lambda d: handle_welcome_event(d, True))

for ev_l in ("member_leave", "server_member_remove", "guild_member_remove"):
    bot.on(ev_l)(lambda d: handle_welcome_event(d, False))
    @bot.command(name="modroles", description="Add or remove a staff role for tickets (or leave empty to view)")
def modroles_cmd(ctx):
    if is_cmd_disabled(ctx.server_id, "modroles"):
        return ctx.ephemeral("`/modroles` is disabled on the web dashboard for this server.")
    if not is_staff(ctx.server_id, ctx.user_id):
        return ctx.ephemeral("Only server admins can manage Mod roles.")
    all_cfg = load_all_cfg()
    sc = get_scfg(ctx.server_id)
    rid = re.sub(r"[<@&>]", "", cmd_text(ctx)).strip()
    if rid:
        if rid in sc["roles"]:
            sc["roles"].remove(rid)
            msg = f"Removed <@&{rid}> from TicketMint Mod roles."
        else:
            sc["roles"].append(rid)
            msg = f"Added <@&{rid}> to TicketMint Mod roles."
        all_cfg[str(ctx.server_id)] = sc
        save_all_cfg(all_cfg)
        return ctx.reply(msg)
    cur = ", ".join(f"<@&{r}>" for r in sc["roles"]) if sc["roles"] else "None set yet"
    ctx.reply(f"**Current Mod Roles:** {cur}\nUse `/modroles @RoleName` or configure on {SITE_URL}/dashboard")

@bot.command(name="ticketpanel", description="Post the orange Open a Ticket panel in this channel")
def ticketpanel_cmd(ctx):
    if is_cmd_disabled(ctx.server_id, "ticketpanel"):
        return ctx.ephemeral("`/ticketpanel` is disabled on the web dashboard for this server.")
    if not is_staff(ctx.server_id, ctx.user_id):
        return ctx.ephemeral("Only server admins can post the ticket panel.")
    target_cid = re.sub(r"[<#>]", "", cmd_text(ctx)).strip() or ctx.channel_id
    send_ticket_panel(target_cid)
    all_cfg = load_all_cfg()
    sc = get_scfg(ctx.server_id)
    sc["dash"] = target_cid
    all_cfg[str(ctx.server_id)] = sc
    save_all_cfg(all_cfg)
    ctx.ephemeral(f"Ticket panel posted in <#{target_cid}>!")

@bot.command(name="claimticket", description="Claim the current open ticket")
def claimticket_cmd(ctx):
    if is_cmd_disabled(ctx.server_id, "claimticket"):
        return ctx.ephemeral("`/claimticket` is disabled on the web dashboard for this server.")
    if not is_staff(ctx.server_id, ctx.user_id):
        return ctx.ephemeral("Only staff members can claim tickets.")
    uname = get_uname(getattr(ctx, "author", None), "Staff")
    ctx.reply(f"Ticket claimed by <@{ctx.user_id}> (**{uname}**).")

@bot.command(name="ticketclose", description="Close and delete the current ticket channel")
def ticketclose_cmd(ctx):
    if is_cmd_disabled(ctx.server_id, "ticketclose"):
        return ctx.ephemeral("`/ticketclose` is disabled on the web dashboard for this server.")
    if not is_staff(ctx.server_id, ctx.user_id):
        return ctx.ephemeral("Only staff members can close tickets.")
    reason = cmd_text(ctx) or "Resolved"
    ctx.reply(f"Closing ticket in 3 seconds... (**Reason:** {reason})")
    close_ticket_now(ctx.server_id, ctx.channel_id, ctx.user_id, reason)

@bot.command(name="setwelcomechannel", description="Set the welcome channel for automatic welcome cards")
def setwelcome_cmd(ctx):
    if is_cmd_disabled(ctx.server_id, "setwelcomechannel"):
        return ctx.ephemeral("`/setwelcomechannel` is disabled on the web dashboard for this server.")
    if not is_staff(ctx.server_id, ctx.user_id):
        return ctx.ephemeral("Only server admins can set the welcome channel.")
    w_cid = re.sub(r"[<#>]", "", cmd_text(ctx)).strip() or ctx.channel_id
    all_cfg = load_all_cfg()
    sc = get_scfg(ctx.server_id)
    sc["welcome"] = w_cid
    all_cfg[str(ctx.server_id)] = sc
    save_all_cfg(all_cfg)
    ctx.reply(f"Welcome channel saved as <#{w_cid}>!")
    @bot.button("ticket_open:")
def on_ticket_open(i):
    kind = i.custom_id.partition(":")[-1] or "support"
    titles = {"support": "General Help", "report": "Report Someone", "appeal": "Punishment Appeal"}
    i.show_modal({
        "custom_id": f"ticket_modal:{kind}",
        "title": titles.get(kind, "Open a Ticket"),
        "components": [
            {"type": "row", "components": [{"type": "text_input", "custom_id": "subject", "label": "Subject / User", "style": "short", "required": True, "max_length": 80}]},
            {"type": "row", "components": [{"type": "text_input", "custom_id": "details", "label": "Describe your issue in detail", "style": "paragraph", "required": True, "max_length": 1000}]},
        ],
    })

@bot.on_modal(re.compile(r"^ticket_modal:"))
def on_ticket_modal(i):
    now = time.time()
    if now - OPEN_COOLDOWN.get(i.user_id, 0) < 15:
        return i.ephemeral("Please wait a few seconds before opening another ticket.")
    OPEN_COOLDOWN[i.user_id] = now
    kind = i.custom_id.partition(":")[-1] or "support"
    subj, det = extract_modal_pair(i, "subject", "details")
    subj = subj or "General Inquiry"
    det = det or "No additional details provided."

    sc = get_scfg(i.server_id)
    safe_user = re.sub(r"[^a-z0-9_-]", "", str(getattr(i, "username", "user")).lower())[:14] or "user"
    overwrites = [
        {"id": i.server_id, "type": "role", "deny": ["view_channel"]},
        {"id": i.user_id, "type": "member", "allow": ["view_channel", "send_messages", "read_message_history"]},
    ]
    if BOT_SELF_ID:
        overwrites.append({"id": BOT_SELF_ID, "type": "member", "allow": ["view_channel", "send_messages", "read_message_history", "manage_channels"]})
    for rid in sc["roles"]:
        if rid and rid != i.server_id:
            overwrites.append({"id": rid, "type": "role", "allow": ["view_channel", "send_messages", "read_message_history"]})

    ch_body = {"name": f"{kind}-{safe_user}", "kind": "text", "permission_overwrites": overwrites}
    if sc["cat"]:
        ch_body["parent_id"] = sc["cat"]

    created = u_dict(bot.api("POST", f"/servers/{i.server_id}/channels", ch_body), "channel")
    new_cid = created.get("id")
    if not new_cid and sc["cat"]:
        ch_body.pop("parent_id", None)
        created = u_dict(bot.api("POST", f"/servers/{i.server_id}/channels", ch_body), "channel")
        new_cid = created.get("id")
    if not new_cid:
        fallback_body = {"name": f"{kind}-{safe_user}", "kind": "text"}
        created = u_dict(bot.api("POST", f"/servers/{i.server_id}/channels", fallback_body), "channel")
        new_cid = created.get("id")

    if not new_cid:
        return i.ephemeral("Could not create ticket channel—check that TicketMint has Manage Channels permission.")

    i.ephemeral(f"Private ticket created: <#{new_cid}>")
    mentions = " ".join(f"<@&{r}>" for r in sc["roles"] if r)
    btns = row(btn("Claim Ticket", "ticket:claim", "success"), btn("Close Ticket", "ticket:close", "danger"))
    bot.api("POST", f"/channels/{new_cid}/messages", {
        "content": f"<@{i.user_id}> {mentions}".strip(),
        "embeds": [{
            "title": f"{kind.title()} • {subj}",
            "description": f"**From:** <@{i.user_id}>\n\n**Details:**\n{det}",
            "color": 0xFF7A00,
        }],
        "components": [btns],
    })

def handle_claim(i):
    try:
        sid = getattr(i, "server_id", None) or (getattr(i, "data", {}) or {}).get("server_id")
        if sid and not is_staff(sid, i.user_id):
            return i.ephemeral("Only staff members can claim tickets.")
        uname = get_uname(getattr(i, "author", None), getattr(i, "username", "Staff"))
        i.reply(f"Ticket claimed by <@{i.user_id}> (**{uname}**).")
    except Exception as e:
        print("[Claim Error]:", e)

def handle_close(i):
    try:
        sid = getattr(i, "server_id", None) or (getattr(i, "data", {}) or {}).get("server_id")
        cid = getattr(i, "channel_id", None) or (getattr(i, "data", {}) or {}).get("channel_id")
        if sid and not is_staff(sid, i.user_id):
            return i.ephemeral("Only staff members can close tickets.")
        i.reply("Closing ticket in 3 seconds...")
        if sid:
            close_ticket_now(sid, cid, i.user_id, "Closed via button")
        elif cid:
            time.sleep(3)
            bot.api("DELETE", f"/channels/{cid}")
    except Exception as e:
        print("[Close Error]:", e)

@bot.button("ticket:claim")
def btn_claim_new(i):
    handle_claim(i)

@bot.button("ticket_claim")
def btn_claim_old(i):
    handle_claim(i)

@bot.button("ticket:close")
def btn_close_new(i):
    handle_close(i)

@bot.button("ticket_close")
def btn_close_old(i):
    handle_close(i)

bot.run()
