from playwright.sync_api import sync_playwright
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":390,"height":844})
    # the app counts a visit through the real server
    pg.goto("http://127.0.0.1:8830/"); pg.wait_for_timeout(2500); pg.evaluate("sendUsage()"); pg.wait_for_timeout(800)
    pg.goto("http://127.0.0.1:8830/stats"); pg.wait_for_timeout(500)
    check("the stats page shows a password box", pg.is_visible("input[type=password]"))
    pg.fill("input[type=password]", "wrong-password-0000"); pg.click("button"); pg.wait_for_timeout(600)
    t=pg.inner_text("body")
    check("a wrong password says so (not forbidden)", "not the password" in t and "forbidden" not in t, t[:200])
    pg.fill("input[type=password]", "local-test-key-123"); pg.click("button"); pg.wait_for_timeout(600)
    t=pg.inner_text("body")
    check("the right password shows the table", "Lessons finished" in t and "forbidden" not in t, t[:300])
    check("with the visit just counted", "Last 30 days\t1" in t or "Last 30 days\n1" in t or "Last 30 days 1" in t, t[t.find("Last 30"):t.find("Last 30")+60])
    pg.screenshot(path="usage/stats_page.png")
    b.close()
print(f"{sum(res)}/{len(res)} passed")
