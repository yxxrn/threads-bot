#!/usr/bin/env python3
"""Threads unofficial API client — NO browser, NO chromium.

Proves the web GraphQL API can be called with:
  cookies (sessionid/csrftoken/ds_user_id/mid/ig_did) + tokens scraped
  from the homepage HTML (fb_dtsg, lsd) + TLS impersonation (curl_cffi).

Usage:
  api_client.py feed                     # fetch home feed (read)
  api_client.py profile <username>       # fetch user profile (read)
  api_client.py post "text"              # publish text
  api_client.py reply <pk> "text"        # reply to a post
  api_client.py chain "p1" "p2" ...      # chain with n/N badges
  api_client.py delete <pk>              # delete own post

Session file: --state FILE, or $THREADS_STATE, or ./storage_state.json
"""
import json
import os
import re
import sys
from pathlib import Path

from curl_cffi import requests as creq

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("THREADS_STATE", ROOT / "storage_state.json"))
API = "https://www.threads.com/api/graphql"
APP_ID = "238260118697367"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class ThreadsAPI:
    def __init__(self, state_file=STATE):
        st = json.loads(Path(state_file).read_text())
        self.cookies = {c["name"]: c["value"]
                        for c in st["cookies"] if "threads.com" in c["domain"]}
        self.s = creq.Session(impersonate="chrome")
        self.tokens = {}
        self._bootstrap()

    def _bootstrap(self):
        """GET homepage HTML → scrape fb_dtsg, lsd, build rev, hsi."""
        r = self.s.get("https://www.threads.com/", cookies=self.cookies,
                       headers={"user-agent": UA}, timeout=30)
        html = r.text
        self.tokens = {
            "fb_dtsg": self._g(html, r'"DTSGInitialData",\[\],\{"token":"(.*?)"'),
            "lsd": self._g(html, r'"LSD",\[\],\{"token":"(.*?)"'),
            "rev": self._g(html, r'"__spin_r":(\d+)'),
            "spin_b": self._g(html, r'"__spin_b":"(.*?)"'),
            "hsi": self._g(html, r'"hsi":"(\d+)"'),
            "csrftoken": self.cookies.get("csrftoken", ""),
        }
        ok = all(self.tokens.get(k) for k in ("fb_dtsg", "lsd"))
        print(f"[bootstrap] status={r.status_code} fb_dtsg={'OK' if self.tokens.get('fb_dtsg') else 'MISSING'} "
              f"lsd={'OK' if self.tokens.get('lsd') else 'MISSING'} rev={self.tokens.get('rev')}")
        return ok

    @staticmethod
    def _g(html, pat):
        m = re.search(pat, html)
        return m.group(1) if m else None

    def graphql(self, friendly_name, doc_id, variables, extra=None):
        """Replay a web GraphQL call with minimal anti-bot params."""
        t = self.tokens
        body = {
            "av": "0", "__user": "0", "__a": "1", "__req": "p",
            "dpr": "1", "__ccg": "UNKNOWN",
            "__rev": t["rev"] or "", "__s": "", "__hsi": t["hsi"] or "",
            "__comet_req": "29",
            "fb_dtsg": t["fb_dtsg"] or "",
            "jazoest": str(sum(ord(c) for c in (t["fb_dtsg"] or ""))),
            "lsd": t["lsd"] or "",
            "__spin_r": t["rev"] or "", "__spin_b": t["spin_b"] or "",
            "__spin_t": "", "server_timestamps": "true",
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": friendly_name,
            "variables": json.dumps(variables),
        }
        if doc_id:
            body["doc_id"] = doc_id
        if extra:
            body.update(extra)
        headers = {
            "user-agent": UA,
            "x-ig-app-id": APP_ID,
            "x-csrftoken": t["csrftoken"],
            "x-fb-lsd": t["lsd"] or "",
            "x-asbd-id": "359341",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.threads.com",
            "referer": "https://www.threads.com/",
        }
        r = self.s.post(API, data=body, cookies=self.cookies,
                        headers=headers, timeout=30)
        return r

    def feed(self):
        vars_ = json.loads(Path(ROOT / "feed_vars.json").read_text()) \
            if (ROOT / "feed_vars.json").exists() else None
        if not vars_:
            vars_ = {
                "data": {"pagination_source": "text_post_feed_threads",
                         "reason": "cold_start_fetch"},
                "variant": "for_you",
                "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": True,
            }
        r = self.graphql("BarcelonaFeedDirectQuery", "29230682679857431", vars_)
        print("[feed] status:", r.status_code)
        if r.status_code == 200:
            d = r.json()
            edges = (d.get("data", {}).get("feedData", {}) or {}).get("edges", [])
            print(f"[feed] {len(edges)} posts")
            for e in edges[:5]:
                p = e["node"]["text_post_app_thread"]["thread_items"][0]["post"]
                txt = (p.get("caption") or {}).get("text", "")
                print("   ", p["user"]["username"], "|", txt[:70].replace("\n", " "))
        else:
            print(r.text[:400])
        return r

    def profile(self, username):
        # BarcelonaProfilePageDirectQuery — doc_id from live capture later
        vars_ = {"username": username}
        r = self.graphql("BarcelonaProfilePageDirectQuery", None, vars_)
        print("[profile] status:", r.status_code)
        print(r.text[:500])
        return r

    def post_text(self, text):
        """Publish a text post — pure HTTP, no browser."""
        import time as _t
        import uuid as _u
        from urllib.parse import urlencode
        sess = f"{_u.uuid4().hex[:6]}:{_u.uuid4().hex[:6]}:{_u.uuid4().hex[:6]}"
        tpi = {
            "community_flair_id": None,
            "composer_session_id": str(_u.uuid4()),
            "entry_point": "main_tab_bar",
            "excluded_inline_media_ids": "[]",
            "fediverse_composer_enabled": True,
            "is_genai_invocation_post": False,
            "is_reply_approval_enabled": False,
            "is_spoiler_media": False,
            "link_attachment_url": None,
            "link_preview_default_render_style": None,
            "quoted_post_id": None,
            "reply_control": 0,
            "self_thread_context_id": str(_u.uuid4()),
            "snippet_attachment": None,
            "special_effects_enabled_str": None,
            "tag_header": None,
            "text_with_entities": {"entities": [], "text": text},
        }
        body = {
            "async_publish": "", "audience": "default",
            "barcelona_source_reply_id": "",
            "caption": text,
            "chain_id": "", "chain_index": "", "chain_length": "",
            "creator_geo_gating_info": '{"whitelist_country_codes":[]}',
            "cross_share_info": "", "custom_accessibility_caption": "",
            "gen_ai_detection_method": "", "internal_features": "",
            "is_meta_only_post": "", "is_paid_partnership": "",
            "is_upload_type_override_allowed": "1", "music_params": "",
            "publish_mode": "text_post", "should_include_permalink": "true",
            "text_post_app_info": json.dumps(tpi, separators=(",", ":")),
            "upload_id": str(int(_t.time() * 1000)),
            "web_session_id": sess,
            "jazoest": str(sum(ord(c) for c in (self.tokens["fb_dtsg"] or ""))),
        }
        headers = {
            "user-agent": UA,
            "x-ig-app-id": APP_ID,
            "x-csrftoken": self.cookies.get("csrftoken", ""),
            "x-instagram-ajax": "0",
            "x-asbd-id": "359341",
            "x-web-session-id": sess,
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "origin": "https://www.threads.com",
            "referer": "https://www.threads.com/",
        }
        r = self.s.post(
            "https://www.threads.com/api/v1/media/configure_text_only_post/",
            data=urlencode(body), cookies=self.cookies, headers=headers,
            timeout=30)
        print("[post] status:", r.status_code)
        if r.status_code == 200:
            d = r.json().get("media", {})
            print("[post] pk:", d.get("pk"), "| code:", d.get("code"))
        else:
            print(r.text[:400])
        return r

    def delete_post(self, pk):
        """Delete own post — GraphQL mutation, pure HTTP."""
        r = self.graphql("useBarcelonaDeletePostWWWMutation",
                         "27316812471326955", {"mediaID": str(pk)})
        print("[delete] status:", r.status_code, "|", r.text[:200])
        return r

    def _publish(self, text, reply_to=None, entry_point="main_tab_bar"):
        """Shared publish call (post or reply)."""
        import time as _t
        import uuid as _u
        from urllib.parse import urlencode
        sess = f"{_u.uuid4().hex[:6]}:{_u.uuid4().hex[:6]}:{_u.uuid4().hex[:6]}"
        tpi = {
            "community_flair_id": None,
            "composer_session_id": str(_u.uuid4()),
            "entry_point": entry_point,
            "excluded_inline_media_ids": "[]",
            "fediverse_composer_enabled": True,
            "is_genai_invocation_post": False,
            "is_reply_approval_enabled": False,
            "is_spoiler_media": False,
            "link_attachment_url": None,
            "link_preview_default_render_style": None,
            "quoted_post_id": None,
            "reply_control": 0,
            "self_thread_context_id": str(_u.uuid4()),
            "snippet_attachment": None,
            "special_effects_enabled_str": None,
            "tag_header": None,
            "text_with_entities": {"entities": [], "text": text},
        }
        if reply_to:
            # reply_id in tpi is what actually attaches the reply to the parent
            tpi["reply_id"] = str(reply_to)
        body = {
            "async_publish": "", "audience": "default",
            "barcelona_source_reply_id": str(reply_to) if reply_to else "",
            "caption": text,
            "chain_id": "", "chain_index": "", "chain_length": "",
            "creator_geo_gating_info": '{"whitelist_country_codes":[]}',
            "cross_share_info": "", "custom_accessibility_caption": "",
            "gen_ai_detection_method": "", "internal_features": "",
            "is_meta_only_post": "", "is_paid_partnership": "",
            "is_upload_type_override_allowed": "1", "music_params": "",
            "publish_mode": "text_post", "should_include_permalink": "true",
            "text_post_app_info": json.dumps(tpi, separators=(",", ":")),
            "upload_id": str(int(_t.time() * 1000)),
            "web_session_id": sess,
            "jazoest": str(sum(ord(c) for c in (self.tokens["fb_dtsg"] or ""))),
        }
        headers = {
            "user-agent": UA,
            "x-ig-app-id": APP_ID,
            "x-csrftoken": self.cookies.get("csrftoken", ""),
            "x-instagram-ajax": "0",
            "x-asbd-id": "359341",
            "x-web-session-id": sess,
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "origin": "https://www.threads.com",
            "referer": "https://www.threads.com/",
        }
        r = self.s.post(
            "https://www.threads.com/api/v1/media/configure_text_only_post/",
            data=urlencode(body), cookies=self.cookies, headers=headers,
            timeout=30)
        return r

    def post_text(self, text):
        """Publish a text post — pure HTTP, no browser."""
        r = self._publish(text)
        print("[post] status:", r.status_code)
        if r.status_code == 200:
            d = r.json().get("media", {})
            print("[post] pk:", d.get("pk"), "| code:", d.get("code"))
        else:
            print(r.text[:400])
        return r

    def reply_text(self, parent_pk, text):
        """Reply to a post — pure HTTP, no browser.

        Requires BOTH text_post_app_info.reply_id AND
        barcelona_source_reply_id (missing reply_id → becomes standalone post).
        """
        r = self._publish(text, reply_to=parent_pk, entry_point="post_page")
        print("[reply] status:", r.status_code)
        if r.status_code == 200:
            d = r.json().get("media", {})
            print("[reply] pk:", d.get("pk"), "| code:", d.get("code"))
        else:
            print(r.text[:400])
        return r

    def chain_text(self, parts):
        """Post a REAL chain (n/N badges): part 1 as post, each next as
        self-reply to the previous part. Verified badges 1/2 + 2/2 on web UI.
        """
        import time as _t
        if len(parts) < 2:
            print("[chain] need >= 2 parts")
            return None
        r = self._publish(parts[0])
        if r.status_code != 200:
            print("[chain] part 1 FAILED:", r.text[:300])
            return r
        d = r.json()["media"]
        pks = [d["pk"]]
        print(f"[chain] 1/{len(parts)} pk:", d["pk"], "| code:", d["code"])
        for i, part in enumerate(parts[1:], start=2):
            _t.sleep(4)
            r = self._publish(part, reply_to=pks[-1], entry_point="post_page")
            if r.status_code != 200:
                print(f"[chain] part {i} FAILED (1..{i-1} live):", r.text[:300])
                return r
            d = r.json()["media"]
            pks.append(d["pk"])
            print(f"[chain] {i}/{len(parts)} pk:", d["pk"], "| code:", d["code"])
        return pks


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?",
                    choices=["feed", "profile", "post", "delete", "reply", "chain"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--state", default=str(STATE))
    a = ap.parse_args()
    api = ThreadsAPI(a.state)
    if a.cmd == "feed":
        api.feed()
    elif a.cmd == "profile":
        api.profile(a.args[0])
    elif a.cmd == "post":
        api.post_text(" ".join(a.args))
    elif a.cmd == "delete":
        api.delete_post(a.args[0])
    elif a.cmd == "reply":
        api.reply_text(a.args[0], " ".join(a.args[1:]))
    elif a.cmd == "chain":
        api.chain_text(a.args)
    else:
        print("usage: api_client.py [feed|profile <u>|post <text>|reply <pk> <text>|"
              "chain <p1> <p2> ...|delete <pk>] [--state f]")
