// Background worker for automatic session monitoring
chrome.cookies.onChanged.addListener((changeInfo) => {
  const cookie = changeInfo.cookie;
  if (!changeInfo.removed && (cookie.name === '__Host-sc-a-session' || cookie.name === 'sc-a-session')) {
    if (cookie.domain.includes('snapchat.com')) {
      console.log('[AUTO-SYNC] Detected fresh Snapchat session cookie, syncing to local daemon...');
      fetch('http://127.0.0.1:8765/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accounts_cookie: `__Host-sc-a-session=${cookie.value}`,
          source: 'background_listener'
        })
      }).catch(e => console.log('[AUTO-SYNC] Daemon offline or unreachable:', e));
    }
  }
});
