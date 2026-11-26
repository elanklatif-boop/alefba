// learnalefba.com/<any page>?nostats leaves this device out of the stats, the same switch as the app's own
// (learnalefba.com/?nostats), so it works from the name page, the Yalda page, the guides and the rest too.
// ?nostats=off counts the device again. It's kept on the device, nowhere else.
(function () {
  try {
    var q = new URLSearchParams(location.search);
    if (!q.has("nostats")) return;
    var back = /^(off|0|no)$/i.test(q.get("nostats") || "");
    if (back) localStorage.removeItem("alefba-nostats"); else localStorage.setItem("alefba-nostats", "1");
    q.delete("nostats");
    var rest = q.toString();
    history.replaceState(null, "", location.pathname + (rest ? "?" + rest : "") + location.hash);
    var show = function () {
      var d = document.createElement("div");
      d.id = "nostatsNote"; d.setAttribute("role", "status");
      d.textContent = back ? "This device is counted in your stats again." : "This device is left out of your stats now, on every page. To count it again, add ?nostats=off to a link.";
      d.style.cssText = "position:fixed;left:12px;right:12px;bottom:12px;z-index:999;max-width:520px;margin:0 auto;padding:12px 14px;border-radius:12px;background:#13213f;color:#fff;font:600 15px/1.4 system-ui,sans-serif;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.3)";
      document.body.appendChild(d);
      setTimeout(function () { d.remove(); }, 6000);
    };
    if (document.body) show(); else document.addEventListener("DOMContentLoaded", show);
  } catch (e) {}
})();
