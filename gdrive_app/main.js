const tabSections = { library: el("librarySection"), radio: el("radioSection") };

// Called by auth.js once sign-in + folder setup completes.
async function onSignedIn() {
  el("loginBtn").hidden = true;
  el("userLabel").textContent = "Connected";
  el("app").hidden = false;
  await loadGenres();
  await initRadio();
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    Object.entries(tabSections).forEach(([k, section]) => (section.hidden = k !== btn.dataset.tab));
    if (btn.dataset.tab === "library") {
      el("topTitle").textContent = "My Favorite Things";
      showLibView("genre");
      loadGenres();
    } else {
      el("topTitle").textContent = "Radio";
      el("libBackBtn").hidden = true;
      el("libAddBtn").hidden = true;
    }
  });
});

el("loginBtn").addEventListener("click", login);
