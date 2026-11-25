"""Radar de Desvios: app Streamlit mínimo (sem lógica de negócio)."""

from pathlib import Path

import streamlit as st

from radar.ui import textos

st.set_page_config(page_title=textos.TITULO_APP)

_css = Path(__file__).parent / "radar" / "ui" / "estilo.css"
if _css.exists():
    st.markdown(f"<style>{_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

st.title(textos.TITULO_APP)
st.write(textos.STATUS_APP)
