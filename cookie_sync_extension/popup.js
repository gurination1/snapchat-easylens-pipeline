document.getElementById('syncBtn').addEventListener('click', async () => {
  const btn = document.getElementById('syncBtn');
  const status = document.getElementById('status');

  btn.disabled = true;
  btn.textContent = 'Extracting cookies...';
  status.className = 'info';
  status.style.display = 'block';
  status.textContent = 'Reading Snapchat session cookies...';

  try {
    const cookies = await chrome.cookies.getAll({ domain: 'snapchat.com' });
    if (!cookies || cookies.length === 0) {
      status.className = 'error';
      status.textContent = 'No Snapchat cookies found. Please log in to accounts.snapchat.com first.';
      btn.disabled = false;
      btn.textContent = 'Sync Session to GitHub';
      return;
    }

    const cookieMap = {};
    cookies.forEach(c => {
      cookieMap[c.name] = c.value;
    });

    const sessionCookie = cookieMap['__Host-sc-a-session'] || cookieMap['sc-a-session'];
    if (!sessionCookie) {
      status.className = 'error';
      status.textContent = 'Snapchat login session (__Host-sc-a-session) not found. Visit accounts.snapchat.com and log in.';
      btn.disabled = false;
      btn.textContent = 'Sync Session to GitHub';
      return;
    }

    // Build full cookie string
    const cookieStr = Object.entries(cookieMap)
      .map(([k, v]) => `${k}=${v}`)
      .join('; ');

    status.textContent = 'Syncing session to local daemon & GitHub Secrets...';

    // POST to local daemon
    const res = await fetch('http://127.0.0.1:8765/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        accounts_cookie: `__Host-sc-a-session=${sessionCookie}`,
        full_cookie: cookieStr
      })
    });

    if (res.ok) {
      const data = await res.json();
      status.className = 'success';
      status.textContent = `✓ Synced! User: @${data.username}. Fresh ticket minted. GitHub Actions is autonomous for 1 year!`;
    } else {
      const errText = await res.text();
      status.className = 'error';
      status.textContent = `Daemon error: ${errText}`;
    }
  } catch (err) {
    status.className = 'error';
    status.textContent = `Sync failed: ${err.message}. Make sure snap_session_daemon.py is running on port 8765.`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sync Session to GitHub';
  }
});
