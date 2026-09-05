// Renders the persistent left sidebar on every individual screen page, so the
// nav is present everywhere - not just on the post-login launcher. Each screen
// is still its own full page; this just injects identical chrome on load.

import { api, getToken, setToken } from "./api.js";
import { buildNav } from "./nav.js";

const LOGIN_URL = "../../index.html";

// .../screens/<key>/index.html  ->  <key>
function activeKeyFromPath() {
  const m = window.location.pathname.match(/\/screens\/([^/]+)\//);
  return m ? m[1] : "";
}

function buildSidebar(role) {
  const aside = document.createElement("aside");
  aside.className = "sidebar shell-sidebar";
  aside.innerHTML = `
    <div class="sidebar-brand">
      <img src="../../assets/iocl-logo.png" alt="IndianOil" class="brand-mark" />
      <div class="sidebar-brand-text">
        <span class="brand-wordmark">SVR</span>
        <span class="brand-caption">Indian Oil Station</span>
      </div>
    </div>
    <nav id="nav-links" aria-label="Modules"></nav>
    <button type="button" class="shell-signout">Sign out</button>
  `;
  buildNav(aside.querySelector("#nav-links"), role, {
    activeKey: activeKeyFromPath(),
    hrefPrefix: "../../",
  });
  aside.querySelector(".shell-signout").addEventListener("click", async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* clearing locally regardless */
    }
    setToken(null);
    window.location.href = LOGIN_URL;
  });
  return aside;
}

async function mount() {
  if (!getToken()) {
    window.location.href = LOGIN_URL;
    return;
  }
  let me;
  try {
    me = await api.me();
  } catch {
    setToken(null);
    window.location.href = LOGIN_URL;
    return;
  }
  document.body.prepend(buildSidebar(me.role));
  document.body.classList.add("shell-mode");
}

mount();
