const API_BASE = "http://localhost:8000/api"; // change to your deployed backend URL

let authToken = localStorage.getItem("fpl_token");
let currentUsername = localStorage.getItem("fpl_username");

// ---------- element refs ----------
const authPanel = document.getElementById("auth-panel");
const appMain = document.getElementById("app-main");
const appFooter = document.getElementById("app-footer");
const userBar = document.getElementById("user-bar");
const usernameDisplay = document.getElementById("username-display");

const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginError = document.getElementById("login-error");
const registerError = document.getElementById("register-error");

// ---------- auth API calls ----------

async function apiPost(path, body, useAuth = false) {
  const headers = { "Content-Type": "application/json" };
  if (useAuth) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

async function apiGet(path, useAuth = true) {
  const headers = {};
  if (useAuth) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${authToken}` },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

// ---------- auth UI ----------

tabLogin.addEventListener("click", () => {
  tabLogin.classList.add("active");
  tabRegister.classList.remove("active");
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
});

tabRegister.addEventListener("click", () => {
  tabRegister.classList.add("active");
  tabLogin.classList.remove("active");
  registerForm.classList.remove("hidden");
  loginForm.classList.add("hidden");
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.textContent = "";
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  try {
    const data = await apiPost("/auth/login", { username, password });
    onLoginSuccess(data.token, data.username);
  } catch (err) {
    loginError.textContent = err.message;
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  registerError.textContent = "";
  const username = document.getElementById("register-username").value.trim();
  const password = document.getElementById("register-password").value;
  try {
    const data = await apiPost("/auth/register", { username, password });
    onLoginSuccess(data.token, data.username);
  } catch (err) {
    registerError.textContent = err.message;
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  authToken = null;
  currentUsername = null;
  localStorage.removeItem("fpl_token");
  localStorage.removeItem("fpl_username");
  showAuthScreen();
});

function onLoginSuccess(token, username) {
  authToken = token;
  currentUsername = username;
  localStorage.setItem("fpl_token", token);
  localStorage.setItem("fpl_username", username);
  showAppScreen();
}

function showAppScreen() {
  authPanel.classList.add("hidden");
  appMain.classList.remove("hidden");
  appFooter.classList.remove("hidden");
  userBar.classList.remove("hidden");
  usernameDisplay.textContent = currentUsername;
  refreshSquad();
}

function showAuthScreen() {
  authPanel.classList.remove("hidden");
  appMain.classList.add("hidden");
  appFooter.classList.add("hidden");
  userBar.classList.add("hidden");
}

// ---------- squad ----------

async function refreshSquad() {
  const statsEl = document.getElementById("squad-stats");
  const listEl = document.getElementById("squad-list");
  statsEl.textContent = "Loading squad...";
  listEl.innerHTML = "";

  try {
    const data = await apiGet("/squad");
    statsEl.textContent =
      `${data.players.length}/15 players — £${data.total_value}m used, ` +
      `£${data.remaining_budget}m remaining` +
      (data.is_complete ? " — squad complete ✓" : "");

    if (data.players.length === 0) {
      listEl.innerHTML = "<p>No players yet — search below to add some.</p>";
      return;
    }

    data.players.forEach((p) => {
      const row = document.createElement("div");
      row.className = "player-row";
      row.innerHTML = `
        <span>${p.name} — ${p.team} (${p.position}) — £${p.price}m, form ${p.form}</span>
        <button data-id="${p.fpl_id}">Remove</button>
      `;
      row.querySelector("button").addEventListener("click", () => removePlayer(p.fpl_id));
      listEl.appendChild(row);
    });
  } catch (err) {
    statsEl.textContent = `Could not load squad: ${err.message}`;
  }
}

async function removePlayer(fplId) {
  try {
    await apiDelete(`/squad/players/${fplId}`);
    refreshSquad();
  } catch (err) {
    alert(`Could not remove player: ${err.message}`);
  }
}

// ---------- player search ----------

document.getElementById("search-btn").addEventListener("click", searchPlayers);
document.getElementById("search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchPlayers();
});

async function searchPlayers() {
  const q = document.getElementById("search-input").value.trim();
  const resultsEl = document.getElementById("search-results");
  if (!q) return;

  resultsEl.innerHTML = "Searching...";
  try {
    const data = await apiGet(`/players/search?q=${encodeURIComponent(q)}`);
    resultsEl.innerHTML = "";
    if (data.results.length === 0) {
      resultsEl.innerHTML = "<p>No players found.</p>";
      return;
    }
    data.results.forEach((p) => {
      const row = document.createElement("div");
      row.className = "search-result-row";
      row.innerHTML = `
        <span>${p.name} — ${p.team} (${p.position}) — £${p.price}m</span>
        <button>Add</button>
      `;
      row.querySelector("button").addEventListener("click", () => addPlayer(p.name));
      resultsEl.appendChild(row);
    });
  } catch (err) {
    resultsEl.innerHTML = `<p>Search failed: ${err.message}</p>`;
  }
}

async function addPlayer(name) {
  try {
    await apiPost("/squad/players", { name }, true);
    document.getElementById("search-results").innerHTML = "";
    document.getElementById("search-input").value = "";
    refreshSquad();
  } catch (err) {
    alert(`Could not add player: ${err.message}`);
  }
}

// ---------- AI advice ----------

document.getElementById("transfer-advice-btn").addEventListener("click", async () => {
  const position = document.getElementById("position-select").value;
  const maxPrice = parseFloat(document.getElementById("max-price-input").value);
  const resultEl = document.getElementById("transfer-advice-result");

  if (isNaN(maxPrice)) {
    resultEl.textContent = "Enter a valid max price first.";
    return;
  }

  resultEl.textContent = "Asking Gemini for advice...";
  try {
    const data = await apiPost("/advice/transfer", { position, max_price: maxPrice }, true);
    resultEl.textContent = data.advice;
  } catch (err) {
    resultEl.textContent = `Could not get advice: ${err.message}`;
  }
});

document.getElementById("captain-advice-btn").addEventListener("click", async () => {
  const resultEl = document.getElementById("captain-advice-result");
  resultEl.textContent = "Asking Gemini for advice...";
  try {
    const data = await apiGet("/advice/captain");
    resultEl.textContent = data.advice;
  } catch (err) {
    resultEl.textContent = `Could not get advice: ${err.message}`;
  }
});

// ---------- init ----------

if (authToken && currentUsername) {
  showAppScreen();
} else {
  showAuthScreen();
}
