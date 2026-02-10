import base64
import streamlit as st
import streamlit.components.v1 as components
from string import Template

st.set_page_config(page_title="Streamlit Parkour", layout="centered")
st.title("🏃 Streamlit Parkour")

col1, col2, col3 = st.columns(3)
with col1:
    difficulty = st.slider("Difficulty", 1, 10, 4)
with col2:
    speed_mult = st.slider("Speed", 1.0, 3.0, 1.6, 0.1)
with col3:
    gravity_mult = st.slider("Gravity", 0.6, 2.4, 1.2, 0.1)

reset = st.button("🔄 Reset Game")
st.session_state["reset_key"] = st.session_state.get("reset_key", 0) + (1 if reset else 0)
reset_key = st.session_state["reset_key"]

# IMPORTANT: Use Template ($vars) and NEVER f-string/format for HTML/JS-heavy content.
html = Template(r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body { margin: 0; padding: 0; background: #0b1020; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; }
    .wrap { width: 760px; max-width: 100%; margin: 0 auto; padding: 8px 0 0 0; color: #e8eefc; }
    .hud {
      display:flex; justify-content:space-between; align-items:center; gap:10px;
      padding: 8px 10px; margin: 6px 0 10px 0;
      background: rgba(255,255,255,0.06);
      bor

