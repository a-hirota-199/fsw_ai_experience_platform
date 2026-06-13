"""Streamlit 対話チャット（Sprint 0）。

要件構造化フローの一周を体験する最小UI。backend の /chat/structure を叩くだけの薄いクライアント。

起動例（リポジトリ直下）:
    BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py
"""
import json
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # リポジトリ直下の .env を自動読込（BACKEND_URL 等）

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="FSW AI 体験版 — 要件構造化", page_icon="🛰️", layout="centered")

# design.md（Anthropic Claude.com デザインシステム）準拠の editorial スタイル。
# 本家の Copernicus/StyreneB はライセンス書体のため、代替に Cormorant Garamond(serif表示)/
# Inter(本文)/JetBrains Mono(コード) を使用（design.md「Note on Font Substitutes」）。
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

st.title("🛰️ 要件構造化チャット（Sprint 0）")
st.caption("ミッション要件を自然言語で入力すると、AIが質問しながら構造化します。")

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
    st.session_state.messages.append({"role": "assistant", "content": data.get("message", "")})
