const tabSections = { library: el("librarySection"), radio: el("radioSection") };

// Called by auth.js once sign-in + folder setup completes.
async function onSignedIn() {
  el("loginBtn").hidden = true;
  el("userLabel").textContent = "Connected";
  el("app").hidden = false;
  await loadGenres();
  await initRadio();
}

// Called by auth.js when there's no way to reach Google - shows whatever's
// already been downloaded for offline use instead.
async function onOfflineMode() {
  await loadOfflineGenres();
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    Object.entries(tabSections).forEach(([k, section]) => (section.hidden = k !== btn.dataset.tab));
    if (btn.dataset.tab === "library") {
      el("topTitle").textContent = "My Favorite Things";
      showLibView("genre");
      if (isOfflineMode) loadOfflineGenres(); else loadGenres();
    } else {
      el("topTitle").textContent = "Radio";
      el("libBackBtn").hidden = true;
      el("libAddBtn").hidden = true;
      if (isOfflineMode) {
        el("radioStatus").textContent = "Radio needs an internet connection, so it's not available offline.";
        el("radioResults").innerHTML = "";
      }
    }
  });
});

el("loginBtn").addEventListener("click", login);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch((err) => console.error("Service worker registration failed", err));
}
