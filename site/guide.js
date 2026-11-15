// The guide pages' two small jobs. 1) A play button (any element with data-a="audio/…mp3") plays that recording,
// one at a time. 2) Two daily totals for the stats page, the same way the app counts (nothing that identifies anyone):
// guide_open when a guide page is opened, guide_start when someone taps through to the app (a link with data-go).
(function () {
  function count(e) {
    try {
      if (localStorage.getItem("alefba-nostats") === "1") return; // this device is left out of the totals (learnalefba.com/?nostats)
      var d = new Date(), day = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
      var body = JSON.stringify({ e: [e], d: day });
      fetch("api/usage", { method: "POST", headers: { "content-type": "application/json" }, body: body, keepalive: true, credentials: "same-origin" }).catch(function () {});
    } catch (x) {}
  }
  var audio = null, btn = null;
  function stop() { if (audio) { audio.pause(); audio = null; } if (btn) { btn.classList.remove("on"); btn = null; } }
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-a]");
    if (b) {
      ev.preventDefault();
      var again = b === btn;
      stop();
      if (again) return; // a second tap stops it
      btn = b; b.classList.add("on");
      audio = new Audio(b.getAttribute("data-a"));
      audio.onended = audio.onerror = function () { if (btn === b) stop(); };
      var p = audio.play();
      if (p && p.catch) p.catch(function () { if (btn === b) stop(); });
      return;
    }
    var a = ev.target.closest && ev.target.closest("a[data-go]");
    if (a) count("guide_start");
  });
  count("guide_open");
})();
