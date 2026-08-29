"""Server-rendered pages the Backend Service hosts directly.

The password-reset landing page is served here (not by the Electron frontend)
because the link is opened from an email client in a normal browser, which cannot
reach the desktop app - only the loopback API. Self-contained: no external assets.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["pages"])

_RESET_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SVR IOCL Station - Set New Password</title>
<style>
  body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f6fb;margin:0;padding:40px;color:#1a1a1a}
  .card{max-width:380px;margin:40px auto;background:#fff;border:1px solid #c9d6ef;border-radius:8px;
        padding:24px;box-shadow:0 2px 10px rgba(0,0,0,.08)}
  h1{font-size:16px;color:#00246e;margin:0 0 8px}
  p.note{font-size:12px;color:#00246e;margin:0 0 14px}
  label{display:block;font-size:11px;color:#0033a0;font-weight:600;margin:10px 0 3px}
  input{width:100%;box-sizing:border-box;padding:8px;border:1px solid #c9d6ef;border-radius:4px;font-size:13px}
  button{margin-top:16px;background:#0033a0;color:#fff;border:0;border-radius:4px;padding:9px 14px;
         font-size:13px;font-weight:700;cursor:pointer}
  button:disabled{opacity:.5}
  #msg{font-size:12px;min-height:16px;margin-top:10px}
  .ok{color:#157347}.err{color:#e31e24}
</style></head><body>
<div class="card">
  <h1>Set a New Password</h1>
  <p class="note">This link is single-use and time-limited. No one else ever sees your password.</p>
  <form id="f">
    <label for="p1">New Password</label>
    <input id="p1" type="password" autocomplete="new-password" required>
    <label for="p2">Confirm New Password</label>
    <input id="p2" type="password" autocomplete="new-password" required>
    <button id="btn" type="submit">Set Password</button>
  </form>
  <p id="msg"></p>
</div>
<script>
  var q = new URLSearchParams(location.search);
  var token = q.get('token') || '';
  var msg = document.getElementById('msg');
  function check(){
    var a = p1.value, b = p2.value;
    if(!a && !b){ msg.textContent=''; return false; }
    if(a.length < 8){ msg.className='err'; msg.textContent='At least 8 characters.'; return false; }
    if(a !== b){ msg.className='err'; msg.textContent='Passwords do not match.'; return false; }
    msg.className='ok'; msg.textContent='Passwords match.'; return true;
  }
  var p1 = document.getElementById('p1'), p2 = document.getElementById('p2');
  p1.addEventListener('input', check); p2.addEventListener('input', check);
  document.getElementById('f').addEventListener('submit', async function(e){
    e.preventDefault();
    if(!token){ msg.className='err'; msg.textContent='Missing token - request a new link.'; return; }
    if(!check()) return;
    document.getElementById('btn').disabled = true;
    try{
      var res = await fetch('/auth/password-reset/confirm', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({token: token, new_password: p1.value})
      });
      if(res.ok){
        document.getElementById('f').style.display='none';
        msg.className='ok'; msg.textContent='Password updated. You can now sign in from the app.';
      } else {
        document.getElementById('btn').disabled = false;
        var d = await res.json().catch(function(){return {};});
        msg.className='err';
        msg.textContent = res.status===400 ? 'This link is invalid or expired - request a new one.'
                                           : (d.detail || 'Could not update the password.');
      }
    }catch(err){
      document.getElementById('btn').disabled = false;
      msg.className='err'; msg.textContent = String(err);
    }
  });
</script></body></html>
"""


@router.get("/password-reset.html", response_class=HTMLResponse)
@router.get("/password-reset", response_class=HTMLResponse)
def password_reset_page() -> str:
    return _RESET_HTML
