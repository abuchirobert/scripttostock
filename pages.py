"""HTML pages: login + admin dashboard (inline, no templates dir needed on Vercel)."""

LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Sign in · ScriptToStock 🎬</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans flex items-center justify-center px-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-8">
      <div class="text-4xl mb-2">🎬</div>
      <h1 class="text-xl font-bold tracking-tight">ScriptToStock</h1>
      <p class="text-xs text-slate-500 mt-1">Sign in to continue</p>
    </div>
    <form onsubmit="doLogin(event)" class="bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
      <div>
        <label class="text-xs text-slate-400 block mb-1">Username</label>
        <input type="text" id="username" autocomplete="username" required
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
      </div>
      <div>
        <label class="text-xs text-slate-400 block mb-1">Password</label>
        <input type="password" id="password" autocomplete="current-password" required
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
      </div>
      <p id="loginError" class="hidden text-xs text-red-400"></p>
      <button type="submit" id="loginBtn"
        class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-xl text-sm transition-colors">
        Sign in
      </button>
      <p class="text-xs text-slate-600 text-center">Access is by invitation only.<br/>Contact the admin for an account.</p>
    </form>
  </div>
  <script>
    async function doLogin(e) {
      e.preventDefault();
      const btn = document.getElementById('loginBtn');
      const err = document.getElementById('loginError');
      btn.disabled = true; btn.textContent = 'Signing in...'; err.classList.add('hidden');
      try {
        const resp = await fetch('/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            username: document.getElementById('username').value.trim(),
            password: document.getElementById('password').value,
          })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Login failed');
        window.location.href = data.is_admin ? '/admin' : '/';
      } catch (ex) {
        err.textContent = ex.message; err.classList.remove('hidden');
        btn.disabled = false; btn.textContent = 'Sign in';
      }
    }
  </script>
</body>
</html>
"""


ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Admin · ScriptToStock 🎬</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans">

  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
    <div class="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-2xl">🎬</span>
        <div>
          <h1 class="text-lg font-bold tracking-tight">ScriptToStock <span class="text-blue-400">Admin</span></h1>
          <p class="text-xs text-slate-500">Users · Credits · API Keys · Usage</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <a href="/" class="text-xs text-slate-400 hover:text-slate-200">← App</a>
        <a href="/logout" class="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg text-slate-300">Log out</a>
      </div>
    </div>
  </header>

  <main class="max-w-6xl mx-auto px-6 py-8 space-y-8">

    <!-- Stats -->
    <div id="statsRow" class="grid grid-cols-2 md:grid-cols-4 gap-3"></div>

    <!-- API Keys & Settings -->
    <section class="bg-slate-900 rounded-2xl border border-slate-800 p-5">
      <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">🔑 API Keys & Pricing</h2>
      <div class="grid md:grid-cols-3 gap-4">
        <div>
          <label class="text-xs text-slate-400 block mb-1">Claude API Key <span id="claudeSet" class="ml-1"></span></label>
          <input type="password" id="claudeKey" placeholder="sk-ant-... (leave blank to keep)"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
        </div>
        <div>
          <label class="text-xs text-slate-400 block mb-1">Pexels API Key <span id="pexelsSet" class="ml-1"></span></label>
          <input type="password" id="pexelsKey" placeholder="Leave blank to keep current"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
        </div>
        <div>
          <label class="text-xs text-slate-400 block mb-1">Markup multiplier (user pays cost × this)</label>
          <input type="number" id="markup" min="1" step="0.5"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
        </div>
      </div>
      <div class="flex items-center gap-3 mt-4">
        <button onclick="saveSettings()" class="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold px-4 py-2 rounded-lg">Save settings</button>
        <button onclick="testKeys()" class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-4 py-2 rounded-lg">Test saved keys</button>
        <span id="settingsMsg" class="text-xs text-slate-500"></span>
      </div>
    </section>

    <!-- Create user -->
    <section class="bg-slate-900 rounded-2xl border border-slate-800 p-5">
      <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">➕ Create User</h2>
      <div class="grid md:grid-cols-4 gap-3">
        <input type="text" id="newUsername" placeholder="username"
          class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
        <input type="text" id="newPassword" placeholder="password"
          class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
        <input type="number" id="newCredit" placeholder="Initial credit ($)" value="5" min="0" step="1"
          class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"/>
        <button onclick="createUser()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-lg">Create user</button>
      </div>
      <p id="createMsg" class="text-xs text-slate-500 mt-2"></p>
    </section>

    <!-- Users table -->
    <section class="bg-slate-900 rounded-2xl border border-slate-800 p-5">
      <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">👥 Users</h2>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-slate-500 uppercase text-left border-b border-slate-800">
              <th class="py-2 pr-4">User</th>
              <th class="py-2 pr-4">Balance</th>
              <th class="py-2 pr-4">Spent</th>
              <th class="py-2 pr-4">Runs</th>
              <th class="py-2 pr-4">Status</th>
              <th class="py-2">Actions</th>
            </tr>
          </thead>
          <tbody id="usersBody"></tbody>
        </table>
      </div>
    </section>

    <!-- Usage log -->
    <section class="bg-slate-900 rounded-2xl border border-slate-800 p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400">📊 Usage History</h2>
        <select id="usageFilter" onchange="loadUsage()" class="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs">
          <option value="">All users</option>
        </select>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-slate-500 uppercase text-left border-b border-slate-800">
              <th class="py-2 pr-4">When</th>
              <th class="py-2 pr-4">User</th>
              <th class="py-2 pr-4">Title</th>
              <th class="py-2 pr-4">Scenes</th>
              <th class="py-2 pr-4">API Cost</th>
              <th class="py-2">Charged</th>
            </tr>
          </thead>
          <tbody id="usageBody"></tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    const fmt = n => '$' + (Number(n) || 0).toFixed(4).replace(/0+$/,'').replace(/\.$/,'.00');
    const fmt2 = n => '$' + (Number(n) || 0).toFixed(2);

    async function api(path, opts) {
      const resp = await fetch(path, Object.assign({headers: {'Content-Type': 'application/json'}}, opts));
      if (resp.status === 401 || resp.status === 403) { window.location.href = '/login'; throw new Error('Session expired'); }
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Request failed');
      return data;
    }

    async function loadAll() {
      const d = await api('/api/admin/overview');
      // Stats
      document.getElementById('statsRow').innerHTML = [
        {label: 'Users', value: d.users.length},
        {label: 'Total runs', value: d.totals.runs},
        {label: 'Charged to users', value: fmt2(d.totals.charged)},
        {label: 'Actual API spend', value: fmt(d.totals.actual)},
      ].map(s => `<div class="bg-slate-900 rounded-xl border border-slate-800 p-4">
          <div class="text-xs text-slate-500">${s.label}</div>
          <div class="text-xl font-bold mt-1">${s.value}</div></div>`).join('');
      // Settings
      document.getElementById('markup').value = d.settings.markup;
      document.getElementById('claudeSet').innerHTML = d.settings.claude_key_set
        ? '<span class="text-emerald-400">● set</span>' : '<span class="text-red-400">● missing</span>';
      document.getElementById('pexelsSet').innerHTML = d.settings.pexels_key_set
        ? '<span class="text-emerald-400">● set</span>' : '<span class="text-red-400">● missing</span>';
      // Users
      const body = document.getElementById('usersBody');
      body.innerHTML = d.users.map(u => `
        <tr class="border-b border-slate-800/50">
          <td class="py-2.5 pr-4 font-medium">${u.username}</td>
          <td class="py-2.5 pr-4 ${u.balance_usd <= 0 ? 'text-red-400 font-bold' : 'text-emerald-300'}">${fmt2(u.balance_usd)}</td>
          <td class="py-2.5 pr-4 text-slate-400">${fmt2(u.total_spent_usd)}</td>
          <td class="py-2.5 pr-4 text-slate-400">${u.runs || 0}</td>
          <td class="py-2.5 pr-4">${u.active
            ? '<span class="text-xs px-2 py-0.5 rounded-full border border-emerald-700 text-emerald-300">active</span>'
            : '<span class="text-xs px-2 py-0.5 rounded-full border border-red-700 text-red-300">revoked</span>'}</td>
          <td class="py-2.5 whitespace-nowrap space-x-1">
            <button onclick="addCredit('${u.username}')" class="text-xs bg-emerald-700 hover:bg-emerald-600 px-2 py-1 rounded">+ Credit</button>
            <button onclick="toggleUser('${u.username}', ${u.active})" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded">${u.active ? 'Revoke' : 'Restore'}</button>
            <button onclick="resetPassword('${u.username}')" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded">Password</button>
            <button onclick="deleteUser('${u.username}')" class="text-xs bg-red-800 hover:bg-red-700 px-2 py-1 rounded">Delete</button>
          </td>
        </tr>`).join('') || '<tr><td colspan="6" class="py-4 text-slate-500 text-xs">No users yet — create one above.</td></tr>';
      // Usage filter options
      const sel = document.getElementById('usageFilter');
      const current = sel.value;
      sel.innerHTML = '<option value="">All users</option>' +
        d.users.map(u => `<option value="${u.username}" ${u.username===current?'selected':''}>${u.username}</option>`).join('');
      loadUsage();
    }

    async function loadUsage() {
      const u = document.getElementById('usageFilter').value;
      const d = await api('/api/admin/usage' + (u ? '?username=' + encodeURIComponent(u) : ''));
      document.getElementById('usageBody').innerHTML = d.usage.map(r => `
        <tr class="border-b border-slate-800/50">
          <td class="py-2 pr-4 text-slate-400 text-xs">${new Date(r.ts * 1000).toLocaleString()}</td>
          <td class="py-2 pr-4">${r.username}</td>
          <td class="py-2 pr-4 text-slate-300">${r.title || '—'}</td>
          <td class="py-2 pr-4 text-slate-400">${r.scenes} (${r.videos}📽 ${r.images}🖼)</td>
          <td class="py-2 pr-4 text-slate-400">${fmt(r.actual_cost_usd)}</td>
          <td class="py-2 text-emerald-300">${fmt(r.charged_usd)}</td>
        </tr>`).join('') || '<tr><td colspan="6" class="py-4 text-slate-500 text-xs">No usage yet.</td></tr>';
    }

    async function saveSettings() {
      const msg = document.getElementById('settingsMsg');
      msg.textContent = 'Saving...';
      try {
        await api('/api/admin/settings', {method: 'POST', body: JSON.stringify({
          claude_key: document.getElementById('claudeKey').value,
          pexels_key: document.getElementById('pexelsKey').value,
          markup: parseFloat(document.getElementById('markup').value) || undefined,
        })});
        document.getElementById('claudeKey').value = '';
        document.getElementById('pexelsKey').value = '';
        msg.textContent = '✓ Saved';
        loadAll();
      } catch (e) { msg.textContent = '✗ ' + e.message; }
    }

    async function testKeys() {
      const msg = document.getElementById('settingsMsg');
      msg.textContent = 'Testing...';
      try {
        const d = await api('/api/admin/test-keys', {method: 'POST'});
        msg.textContent = `Claude: ${d.claude.ok ? '✓' : '✗ ' + d.claude.error} · Pexels: ${d.pexels.ok ? '✓' : '✗ ' + d.pexels.error}`;
      } catch (e) { msg.textContent = '✗ ' + e.message; }
    }

    async function createUser() {
      const msg = document.getElementById('createMsg');
      try {
        await api('/api/admin/users', {method: 'POST', body: JSON.stringify({
          username: document.getElementById('newUsername').value.trim(),
          password: document.getElementById('newPassword').value,
          credit: parseFloat(document.getElementById('newCredit').value) || 0,
        })});
        msg.textContent = '✓ User created';
        document.getElementById('newUsername').value = '';
        document.getElementById('newPassword').value = '';
        loadAll();
      } catch (e) { msg.textContent = '✗ ' + e.message; }
    }

    async function addCredit(username) {
      const amt = prompt(`Add credit ($) to ${username}: (minimum allocation is $5)`, '5');
      if (amt === null) return;
      await api(`/api/admin/users/${encodeURIComponent(username)}/credit`, {method: 'POST', body: JSON.stringify({amount: parseFloat(amt)})});
      loadAll();
    }

    async function toggleUser(username, active) {
      if (active && !confirm(`Revoke access for ${username}?`)) return;
      await api(`/api/admin/users/${encodeURIComponent(username)}/toggle`, {method: 'POST'});
      loadAll();
    }

    async function resetPassword(username) {
      const pw = prompt(`New password for ${username}:`);
      if (!pw) return;
      await api(`/api/admin/users/${encodeURIComponent(username)}/password`, {method: 'POST', body: JSON.stringify({password: pw})});
      alert('Password updated.');
    }

    async function deleteUser(username) {
      if (!confirm(`Permanently delete ${username} and their usage history?`)) return;
      await api(`/api/admin/users/${encodeURIComponent(username)}`, {method: 'DELETE'});
      loadAll();
    }

    loadAll().catch(e => alert(e.message));
  </script>
</body>
</html>
"""
