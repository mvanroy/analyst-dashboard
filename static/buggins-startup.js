(() => {
  "use strict";

  const body = document.body;
  const hiddenKey = "buggins-hidden-at-v8";
  const recoveryKey = "buggins-recovery-at-v8";
  const reloadingKey = "buggins-reloading-v8";
  let initialLoad = true;
  let tapWatchdog = 0;
  let tapStartGuard = 0;
  let markerAtTap = null;
  let sawRunAfterTap = false;
  let statusTimer = 0;
  let jumpScrollHost = null;

  sessionStorage.removeItem(reloadingKey);

  const streamlitRunState = () =>
    document.querySelector('[data-testid="stApp"]')?.dataset.testScriptState || "";

  const streamlitConnectionState = () =>
    document.querySelector('[data-testid="stApp"]')?.dataset.testConnectionState || "";

  const appIsReady = () => Boolean(
    streamlitRunState() === "notRunning" ||
    document.querySelector(".buggins-login-title") ||
    document.querySelector('[data-testid="stAlert"]')
  );

  const showStartup = () => {
    body.classList.remove("buggins-ready");
    body.classList.add("buggins-loading");
  };

  const hideStartup = () => {
    body.classList.remove("buggins-loading");
    body.classList.add("buggins-ready");
    initialLoad = false;
    installJumpNavigation();
  };

  const readyPoll = window.setInterval(() => {
    if (!appIsReady()) return;
    window.clearInterval(readyPoll);
    window.requestAnimationFrame(hideStartup);
  }, 40);
  // Never expose Streamlit's half-built grid. If a run cannot finish, recover
  // behind the navy shell instead of showing buttons with no live callbacks.
  window.setTimeout(() => {
    if (appIsReady()) return;
    window.clearInterval(readyPoll);
    recover();
  }, 30000);

  const clearTapWatchdog = () => {
    if (tapWatchdog) window.clearTimeout(tapWatchdog);
    if (tapStartGuard) window.clearTimeout(tapStartGuard);
    tapWatchdog = 0;
    tapStartGuard = 0;
    markerAtTap = null;
    sawRunAfterTap = false;
  };

  const showStatus = (message, blocking = false) => {
    document.getElementById("bl-interaction-status")?.remove();
    if (statusTimer) window.clearTimeout(statusTimer);
    const status = document.createElement("div");
    status.id = "bl-interaction-status";
    status.dataset.blocking = blocking ? "true" : "false";
    status.innerHTML = `<span>${message}</span>`;
    Object.assign(status.style, blocking ? {
      position: "fixed", inset: "0", zIndex: "2147483646",
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(2,10,23,.72)", backdropFilter: "blur(4px)",
      WebkitBackdropFilter: "blur(4px)", pointerEvents: "auto"
    } : {
      position: "fixed", left: "50%", top: "calc(env(safe-area-inset-top) + 12px)",
      transform: "translateX(-50%)", zIndex: "2147483646", pointerEvents: "none"
    });
    Object.assign(status.firstElementChild.style, {
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      minWidth: "112px", minHeight: "42px", padding: "9px 16px",
      border: "1px solid rgba(126,182,255,.48)", borderRadius: "999px",
      background: "#10243d", color: "#f5f7fb", boxShadow: "0 12px 32px rgba(0,0,0,.34)",
      font: "800 14px/1.2 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif"
    });
    body.appendChild(status);
    if (!blocking) {
      statusTimer = window.setTimeout(() => status.remove(), 1800);
    }
  };

  const recover = () => {
    const now = Date.now();
    const lastRecovery = Number(sessionStorage.getItem(recoveryKey) || 0);
    if (now - lastRecovery < 8000) return;
    clearTapWatchdog();
    sessionStorage.setItem(recoveryKey, String(now));
    sessionStorage.setItem(reloadingKey, "1");
    showStartup();
    window.setTimeout(() => window.location.reload(), 40);
  };

  const scrollTop = () => {
    const host = document.querySelector('[data-testid="stMain"]');
    if (host && typeof host.scrollTo === "function") {
      host.scrollTo({top: 0, left: 0, behavior: "auto"});
    }
    window.scrollTo({top: 0, left: 0, behavior: "auto"});
  };

  const onPointerDown = (event) => {
    const target = event.target && typeof event.target.closest === "function"
      ? event.target.closest(
          '[class*="st-key-blcell_"] button, [class*="st-key-bl_toggle_"] button, ' +
          '.st-key-bl_nav_log button, .st-key-bl_nav_analytics button'
        )
      : null;
    if (!target) return;
    clearTapWatchdog();
    markerAtTap = document.querySelector("#bl-app-ready");
    sawRunAfterTap = false;
    const isCell = Boolean(target.closest('[class*="st-key-blcell_"]'));
    const isNav = Boolean(target.closest(".st-key-bl_nav_log, .st-key-bl_nav_analytics"));
    showStatus(isCell ? "Working…" : "Opening…");
    if (isNav) {
      scrollTop();
      window.setTimeout(scrollTop, 100);
    }
    // A healthy Streamlit button begins a rerun almost immediately. Recover
    // quickly only when no rerun starts at all; once a save has started, allow
    // the database request to finish without reloading underneath it.
    tapStartGuard = window.setTimeout(() => {
      if (!tapWatchdog || sawRunAfterTap) return;
      recover();
    }, 3000);
    tapWatchdog = window.setTimeout(recover, 30000);
  };

  const root = document.getElementById("root");
  if (root) {
    const responseObserver = new MutationObserver(() => {
      if (!tapWatchdog) return;
      const markerNow = document.querySelector("#bl-app-ready");
      const runState = streamlitRunState();
      if (runState === "running") sawRunAfterTap = true;
      const pickerOpened = Boolean(
        document.querySelector("#bl-feed-wheel-overlay") ||
        document.querySelector('[class*="st-key-bl_feed_wheel_host_"]')
      );
      if (
        pickerOpened ||
        (sawRunAfterTap && runState === "notRunning") ||
        (markerAtTap && !markerAtTap.isConnected) ||
        markerNow !== markerAtTap
      ) {
        clearTapWatchdog();
      }
    });
    responseObserver.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-test-script-state", "data-test-connection-state"]
    });
  }

  const markHidden = () => {
    clearTapWatchdog();
    if (!sessionStorage.getItem(reloadingKey)) {
      sessionStorage.setItem(hiddenKey, String(Date.now()));
    }
  };

  const resume = (fromCache = false) => {
    if (initialLoad) return;
    sessionStorage.removeItem(hiddenKey);
    if (!navigator.onLine) {
      showStatus("Connection lost", true);
      return;
    }
    document.querySelector('#bl-interaction-status[data-blocking="true"]')?.remove();
    // Time spent in the background is not itself a failure. Preserve the open
    // profile, scroll position and picker whenever Streamlit still reports a
    // live connection. The tap guard remains the fallback for a stale socket.
    window.setTimeout(() => {
      const connectionState = streamlitConnectionState();
      if (connectionState && connectionState !== "CONNECTED") recover();
      else if (fromCache && !connectionState) recover();
    }, 250);
  };

  const onVisibility = () => {
    if (document.visibilityState === "hidden") markHidden();
    else resume(false);
  };

  const updateJumpNavigation = () => {
    const nav = document.querySelector(".bl-mobile-jump-nav");
    if (!nav) return;
    const compact = window.matchMedia("(max-width: 1100px)").matches;
    const openPanels = [...document.querySelectorAll(
      '.st-key-bl_panel_a:has(.bl-panel-state.open), .st-key-bl_panel_b:has(.bl-panel-state.open)'
    )];
    const reachedFiveAm = openPanels.some((panel) => {
      const baby = panel.classList.contains("st-key-bl_panel_a") ? "a" : "b";
      const row = document.querySelector(`.st-key-blrow_${baby}_5`);
      return row && row.getBoundingClientRect().top < Math.max(180, Math.min(650, window.innerHeight - 132));
    });
    nav.classList.toggle("is-active", compact && reachedFiveAm);
  };

  function installJumpNavigation() {
    const host = document.querySelector('[data-testid="stMain"]') || window;
    if (host === jumpScrollHost) return;
    if (jumpScrollHost) jumpScrollHost.removeEventListener("scroll", updateJumpNavigation);
    jumpScrollHost = host;
    jumpScrollHost.addEventListener("scroll", updateJumpNavigation, {passive: true});
    updateJumpNavigation();
  }

  document.addEventListener("pointerdown", onPointerDown, true);
  document.addEventListener("visibilitychange", onVisibility, {passive: true});
  window.addEventListener("pagehide", markHidden, {passive: true});
  window.addEventListener("pageshow", (event) => resume(Boolean(event.persisted)), {passive: true});
  window.addEventListener("online", () => resume(false), {passive: true});
  window.addEventListener("offline", () => showStatus("Connection lost", true), {passive: true});
  window.addEventListener("resize", updateJumpNavigation, {passive: true});
  window.addEventListener("orientationchange", updateJumpNavigation, {passive: true});
})();
