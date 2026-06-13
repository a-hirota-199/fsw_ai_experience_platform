"""Streamlit 対話チャット（Sprint 0）。

要件構造化フローの一周を体験する最小UI。backend の /chat/structure を叩くだけの薄いクライアント。

起動例（リポジトリ直下）:
    BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py
"""
import io
import json
import os
import zipfile

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # リポジトリ直下の .env を自動読込（BACKEND_URL 等）

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="FSW AI 体験版 — 要件構造化", page_icon="🛰️", layout="centered")

# .claude/skills/web-design/SKILL.md（Anthropic Claude.com デザインシステム）準拠の editorial スタイル。
# 本家の Copernicus/StyreneB はライセンス書体のため、代替に Cormorant Garamond(serif表示)/
# Inter(本文)/JetBrains Mono(コード) を使用（SKILL.md「Note on Font Substitutes」）。
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root{
  --canvas:#faf9f5; --surface-soft:#f5f0e8; --surface-card:#efe9de; --cream-strong:#e8e0d2;
  --dark:#181715; --ink:#141413; --body:#3d3d3a; --muted:#6c6a64;
  --hairline:#e6dfd8; --primary:#cc785c; --primary-active:#a9583e; --on-primary:#ffffff;
}

.stApp{ background:var(--canvas); }
.stApp, .stApp p, .stApp li, .stApp label,
[data-testid="stMarkdownContainer"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  color:var(--body);
}
.block-container{ max-width:820px; padding-top:3rem; }

/* 見出し: serif display（weight控えめ・負の字間） */
h1,h2,h3{
  font-family:'Cormorant Garamond',Georgia,'Times New Roman',serif !important;
  color:var(--ink) !important; font-weight:600 !important;
  letter-spacing:-0.5px; line-height:1.12;
}
h1{ font-size:2.8rem !important; }

[data-testid="stCaptionContainer"]{ color:var(--muted) !important; }

/* チャットメッセージ = cream カード（hairline 境界・角丸12） */
[data-testid="stChatMessage"]{
  background:var(--surface-card); border:1px solid var(--hairline);
  border-radius:12px; padding:14px 18px; margin-bottom:12px;
}
/* user 発話 = canvas + 細い coral アクセント（coral は希少に） */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){
  background:var(--canvas); border-left:3px solid var(--primary);
}

/* 入力欄: hairline 境界・角丸 */
[data-testid="stChatInput"]{
  background:var(--canvas); border:1px solid var(--hairline); border-radius:10px;
}
[data-testid="stChatInput"] textarea{ color:var(--ink); }

/* ボタン（ダウンロード等）= coral primary */
.stButton>button, [data-testid="stDownloadButton"]>button{
  background:var(--primary) !important; color:var(--on-primary) !important;
  border:none !important; border-radius:8px !important;
  font-family:'Inter',sans-serif !important; font-weight:500 !important;
}
.stButton>button:hover, [data-testid="stDownloadButton"]>button:hover{
  background:var(--primary-active) !important; color:#fff !important;
}

/* 構造化要件 JSON: soft cream カード + 等幅 */
[data-testid="stJson"]{
  background:var(--surface-soft) !important; border:1px solid var(--hairline);
  border-radius:12px; padding:14px;
}
[data-testid="stJson"] *{ font-family:'JetBrains Mono',ui-monospace,monospace !important; }

[data-testid="stAlert"]{ border-radius:10px; }

/* Streamlit 既定クロームを抑える */
#MainMenu{ visibility:hidden; }
footer{ visibility:hidden; }
[data-testid="stHeader"]{ background:transparent; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

st.title("🛰️ 要件 → cFSアプリ生成")
st.caption("ミッション要件を自然言語で入力 → AIが構造化 → cFSアプリの骨格コードを生成します。")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("例: 姿勢データを5Hzでテレメトリ送出したい"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat/structure",
            json={"messages": st.session_state.messages},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        data = {"mode": "ask", "message": f"backend接続エラー: {e}", "requirement": None}

    with st.chat_message("assistant"):
        st.markdown(data.get("message", ""))
        if data.get("requirement"):
            st.success("構造化要件が確定しました")
            st.json(data["requirement"])
            st.download_button(
                "要件JSONをダウンロード",
                data=json.dumps(data["requirement"], ensure_ascii=False, indent=2),
                file_name="requirement.json",
                mime="application/json",
            )
            # 確定要件を保存し、旧い生成・公開結果は破棄（要件が変わったため）
            st.session_state.requirement = data["requirement"]
            st.session_state.pop("generated", None)
            st.session_state.pop("published", None)
    st.session_state.messages.append({"role": "assistant", "content": data.get("message", "")})


# --- コード生成セクション（要件が確定している時に表示） ---
req = st.session_state.get("requirement")
if req:
    st.divider()
    st.subheader("コード生成")
    st.caption(f"確定要件: **{req.get('app_name', 'app')}** — cFSアプリの骨格を生成します。")
    if st.button("🛠 このアプリのcFSコードを生成"):
        try:
            r = requests.post(f"{BACKEND_URL}/generate", json={"requirement": req}, timeout=180)
            r.raise_for_status()
            st.session_state.generated = r.json()
            st.session_state.pop("published", None)  # 再生成したら旧い公開結果は破棄
        except requests.RequestException as e:
            st.session_state.generated = {
                "app_name": req.get("app_name", ""),
                "files": [],
                "notes": [f"生成エラー: {e}"],
            }

gen = st.session_state.get("generated")
if gen:
    for n in gen.get("notes", []):
        st.caption("・" + n)
    for f in gen.get("files", []):
        path = f["path"]
        lang = "c" if path.endswith((".c", ".h")) else ("cmake" if "CMakeLists" in path else "text")
        with st.expander(path, expanded=path.endswith("_app.c")):
            st.code(f["content"], language=lang)
    if gen.get("files"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in gen["files"]:
                z.writestr(f["path"], f["content"])
        st.download_button(
            "📦 全ファイルをZIPでダウンロード",
            data=buf.getvalue(),
            file_name=f"{gen.get('app_name', 'app')}.zip",
            mime="application/zip",
        )

        # --- GitHub 公開セクション（branch+PR） ---
        st.divider()
        st.subheader("GitHub に公開")
        st.caption("生成物を指定リポジトリに `feat/<app>` ブランチで push し、PR を起票します。")
        if st.button("🚀 GitHubにPRを作成"):
            payload = {
                "app_name": gen.get("app_name", ""),
                "files": gen.get("files", []),
                "summary": (req or {}).get("summary", ""),
            }
            try:
                r = requests.post(f"{BACKEND_URL}/publish", json=payload, timeout=120)
                r.raise_for_status()
                st.session_state.published = r.json()
            except requests.RequestException as e:
                st.session_state.published = {"ok": False, "message": f"公開エラー: {e}"}

        pub = st.session_state.get("published")
        if pub:
            if pub.get("ok"):
                st.success(pub.get("message", ""))
                if pub.get("pr_url"):
                    st.markdown(f"**PR:** [{pub['pr_url']}]({pub['pr_url']})")
                if pub.get("branch"):
                    st.caption(f"branch: `{pub['branch']}` / repo: `{pub.get('repo', '')}`")
            else:
                st.error(pub.get("message", "公開に失敗しました"))
