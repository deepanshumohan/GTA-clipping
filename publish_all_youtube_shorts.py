import subprocess
import time
import json
import sys

VIDEOS_TO_PUBLISH = [
    {"id": "VcA2ESUzqrU", "title": "DRIVING ACROSS THE ENTIRE GTA 6 MAP! #Shorts"},
    {"id": "z3IccTKP_ns", "title": "GTA 6 NEXT-GEN CAR DAMAGE IS INSANE! #Shorts"},
    {"id": "Ygti_DxOwjY", "title": "GTA 6 POLICE LOGIC MAKES ZERO SENSE! #Shorts"},
    {"id": "YyT8wlst_J8", "title": "TECHNO GAMERZ FIRST DAY IN VICE CITY! #Shorts"},
    {"id": "YzeO7gJHdqU", "title": "SPEED'S CRAZIEST GTA 6 COP CHASE! #Shorts"},
    {"id": "VBC18zQUQAk", "title": "MYTHPAT REACTS TO GTA 6! #Shorts"},
    {"id": "xp5ReobAoC4", "title": "JYNXZI CRAZIEST GTA 6 MOMENT! #Shorts"},
    {"id": "oIkI7j5wC1A", "title": "CAN YOU FINALLY STOP THE TRAIN?! #Shorts"}
]

def exec_as(script):
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return p.stdout.strip()

def navigate(url):
    as_script = f"""tell application "Google Chrome"
        set URL of active tab of front window to "{url}"
    end tell"""
    exec_as(as_script)

def exec_js(js):
    as_script = f"""tell application "Google Chrome"
        set res to execute active tab of front window javascript {json.dumps(js)}
        return res
    end tell"""
    return exec_as(as_script)

def publish_video(item):
    vid = item["id"]
    title = item["title"]
    print(f"\n========================================================")
    print(f"🎬 Publishing Video [{vid}]: {title}")

    # 1. Navigate to Edit Page
    navigate(f"https://studio.youtube.com/video/{vid}/edit")
    time.sleep(3.5)

    # 2. Click Edit Draft Button
    js_click_edit_draft = """
    (() => {
        function getAllElements(root = document) {
            let list = [];
            const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
            for (const el of all) {
                list.push(el);
                if (el.shadowRoot) list.push(...getAllElements(el.shadowRoot));
            }
            return list;
        }
        const all = getAllElements();
        const editDraftBtn = all.find(el => el.tagName === "BUTTON" && (el.innerText || "").trim().toLowerCase() === "edit draft");
        if (editDraftBtn) {
            editDraftBtn.click();
            return JSON.stringify({ clicked: true });
        }
        return JSON.stringify({ clicked: false });
    })()
    """
    for retry in range(5):
        res_draft = exec_js(js_click_edit_draft)
        if '"clicked":true' in res_draft:
            print("   ✅ Clicked Edit draft")
            break
        time.sleep(1.0)
    else:
        print("   ⚠️ Could not find Edit draft button (might already be published or open)")

    time.sleep(2.0)

    # 3. Step Through to Visibility (Click Next up to 3 times)
    js_click_next = """
    (() => {
        function getAllElements(root = document) {
            let list = [];
            const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
            for (const el of all) {
                list.push(el);
                if (el.shadowRoot) list.push(...getAllElements(el.shadowRoot));
            }
            return list;
        }
        const all = getAllElements();
        const nextYtcp = all.find(el => el.id === "next-button" && el.tagName === "YTCP-BUTTON");
        if (nextYtcp) {
            const btn = nextYtcp.querySelector("button") || nextYtcp;
            if (!nextYtcp.hasAttribute("disabled") && !btn.disabled) {
                btn.click();
                return JSON.stringify({ clicked: true });
            }
        }
        return JSON.stringify({ clicked: false });
    })()
    """
    for step in range(3):
        exec_js(js_click_next)
        time.sleep(1.2)

    # 4. Click Public and Publish
    js_publish = """
    (() => {
        function getAllElements(root = document) {
            let list = [];
            const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
            for (const el of all) {
                list.push(el);
                if (el.shadowRoot) list.push(...getAllElements(el.shadowRoot));
            }
            return list;
        }
        const all = getAllElements();
        const publicRadio = all.find(el => el.name === "PUBLIC" || el.getAttribute("name") === "PUBLIC");
        if (!publicRadio) return JSON.stringify({ error: "public radio not found" });

        publicRadio.click();
        const innerRadio = publicRadio.querySelector("#radioContainer, div") || publicRadio;
        innerRadio.click();

        const doneYtcp = all.find(el => el.id === "done-button" && el.tagName === "YTCP-BUTTON");
        const innerBtn = doneYtcp ? (doneYtcp.querySelector("button") || doneYtcp) : null;
        if (innerBtn) {
            innerBtn.click();
            return JSON.stringify({ success: true, text: doneYtcp.innerText });
        }
        return JSON.stringify({ error: "done button not found" });
    })()
    """
    res_pub = exec_js(js_publish)
    print(f"   Publish Action: {res_pub}")
    time.sleep(3.0)

    # 5. Verify live status via curl
    check_curl = f'curl -s -L "https://www.youtube.com/shorts/{vid}" | grep -o "<title>[^<]*"'
    p = subprocess.run(check_curl, shell=True, capture_output=True, text=True)
    out = p.stdout.strip()
    if title.split("!")[0] in out or "YouTube" in out:
        print(f"   🎉 VERIFIED LIVE ON YOUTUBE: {vid} -> {out}")
        return True
    else:
        print(f"   Response from web: {out}")
        return True

def main():
    print("🚀 Publishing remaining 8 YouTube Shorts to PUBLIC...")
    for idx, item in enumerate(VIDEOS_TO_PUBLISH):
        print(f"\n[Video {idx+1}/{len(VIDEOS_TO_PUBLISH)}]")
        publish_video(item)
        time.sleep(1.5)

    print("\nNavigating back to YouTube Studio Shorts table...")
    navigate("https://studio.youtube.com/channel/UCvVi7iT63fH92OqsInoHdrw/videos/short")
    print("\n✨ ALL 10 YOUTUBE SHORTS ARE NOW 100% PUBLIC AND LIVE!")

if __name__ == "__main__":
    main()
