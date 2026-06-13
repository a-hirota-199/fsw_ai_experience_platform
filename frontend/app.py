"""Streamlit 対話チャット（Sprint 0）。

要件構造化フローの一周を体験する最小UI。backend の /chat/structure を叩くだけの薄いクライアント。

起動例（リポジトリ直下）:
    BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py
"""
import json
import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="FSW AI 体験版 — 要件構造化", page_icon="🛰️")
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
