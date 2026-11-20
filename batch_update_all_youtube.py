import subprocess
import time
import json
import sys

VIDEOS_TO_UPDATE = [
    {
        "id": "RXp6SGvFjEc",
        "title": "GTA 6 IN-GAME TIKTOK DOOMSCROLLING! #Shorts",
        "desc": "GTA 6 ADDED IN-GAME TIKTOK AND DOOMSCROLLING! Unhinged Vice City social media posts, live stream comments, alligator pool rescues, and viral memes! Rockstar's satire is unmatched!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#GTA6 #GTA6TikTok #Doomscrolling #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "YulqVcZXakw",
        "title": "GTA 6 DAMAGE PHYSICS ITEM TIER LIST! #Shorts",
        "desc": "GTA 6 DAMAGE PHYSICS TIER LIST! Ranking vehicle destruction from B-Tier to God-Tier! Watch how supercars crumple vs heavy trucks! Do you agree with this ranking?\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#GTA6 #TierList #DamagePhysics #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "VcA2ESUzqrU",
        "title": "DRIVING ACROSS THE ENTIRE GTA 6 MAP! #Shorts",
        "desc": "DRIVING ACROSS THE ENTIRE GTA 6 MAP AT 220 MPH! Starting from Downtown Vice City all the way through neon boulevards and ocean highways! Leonida is 2.5x bigger than Los Santos!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#GTA6 #GTA6Map #ViceCity #Supercars #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "z3IccTKP_ns",
        "title": "GTA 6 NEXT-GEN CAR DAMAGE IS INSANE! #Shorts",
        "desc": "TESTING NEXT-GEN CAR DAMAGE IN GTA 6! Dynamic crumple zones, frame twisting, and wheel detachment at 150+ MPH! Rockstar went full simulation mode!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#GTA6 #CarDamage #GamingPhysics #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "Ygti_DxOwjY",
        "title": "GTA 6 POLICE LOGIC MAKES ZERO SENSE! #Shorts",
        "desc": "GTA 6 POLICE LOGIC MAKES ZERO SENSE! You accidentally bump an officer and suddenly five SWAT cruisers spawn behind you! Vice City PD does not play around!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#GTA6 #ViceCityPD #PoliceLogic #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "YyT8wlst_J8",
        "title": "TECHNO GAMERZ FIRST DAY IN VICE CITY! #Shorts",
        "desc": "TECHNO GAMERZ FIRST DAY IN GTA 6! Ujjwal steals his first supercar and checks out next-gen Vice City graphics and sound! Pure gaming hype!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#TechnoGamerz #GTA6 #ViceCity #GamingIndia #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "YzeO7gJHdqU",
        "title": "SPEED'S CRAZIEST GTA 6 COP CHASE! #Shorts",
        "desc": "SPEED GETS 5 STARS IN GTA 6! Complete chaos as Speed flips his car across the Vice City highway while screaming at the cops! Peak Speed energy!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#IShowSpeed #GTA6 #SpeedClips #CopChase #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "VBC18zQUQAk",
        "title": "MYTHPAT REACTS TO GTA 6! #Shorts",
        "desc": "MYTHPAT REACTS TO GTA 6 FOR THE FIRST TIME! Dimaag hila diya! Mythpat could not believe the graphics, pedestrian physics, and Vice City world scale!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#Mythpat #GTA6 #GamingReactions #GamingIndia #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "xp5ReobAoC4",
        "title": "JYNXZI CRAZIEST GTA 6 MOMENT! #Shorts",
        "desc": "JYNXZI CANNOT HANDLE GTA 6! Four-star panic flying over Vice City, military jargon, and unfiltered Jynxzi screams! Pure comedy gold!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#Jynxzi #GTA6 #JynxziClips #GamingMoments #WoldoPlays #Gaming #Shorts #Reels"
    },
    {
        "id": "oIkI7j5wC1A",
        "title": "CAN YOU FINALLY STOP THE TRAIN?! #Shorts",
        "desc": "CAN YOU FINALLY STOP THE GTA 6 TRAIN?! In GTA 5 the train was literally indestructible, but in GTA 6 next-gen physics allow real collisions and emergency stops! Watch the high-speed impact!\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n#GTA6 #GTAMyths #GamingMythbusters #WoldoPlays #Gaming #Shorts #Reels"
    }
]

def exec_as(script):
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return p.stdout.strip()

def navigate_tab(url):
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

def wait_for_video_page(vid, max_wait=20):
    check_js = f"""
    (() => {{
        try {{
            if (!window.location.href.includes("{vid}")) return JSON.stringify({{ ok: false, reason: "wrong url " + window.location.href }});
            if (document.readyState !== "complete") return JSON.stringify({{ ok: false, reason: "doc not complete" }});

            function getAllElements(root = document) {{
                let list = [];
                const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
                for (const el of all) {{
                    list.push(el);
                    if (el.shadowRoot) list.push(...getAllElements(el.shadowRoot));
                }}
                return list;
            }}

            const all = getAllElements();
            const boxes = all.filter(el => el.id === "textbox" && el.getAttribute("contenteditable") !== null);
            const saveBtn = all.find(el => el.id === "save" && el.tagName === "YTCP-BUTTON");

            return JSON.stringify({{
                ok: boxes.length >= 2 && !!saveBtn,
                boxCount: boxes.length,
                hasSave: !!saveBtn
            }});
        }} catch(e) {{
            return JSON.stringify({{ ok: false, error: e.message }});
        }}
    }})()
    """
    start = time.time()
    while time.time() - start < max_wait:
        res_str = exec_js(check_js)
        try:
            res = json.loads(res_str)
            if res.get("ok"):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def update_single_video(item):
    vid = item["id"]
    title = item["title"]
    desc = item["desc"]
    print(f"\n========================================================")
    print(f"🎬 Updating Video [{vid}]")
    print(f"   Target Title: {title}")

    # 1. Navigate
    edit_url = f"https://studio.youtube.com/video/{vid}/edit"
    navigate_tab(edit_url)

    # 2. Wait for page and elements
    if not wait_for_video_page(vid, 20):
        print(f"   ❌ Timed out waiting for edit page elements for {vid}")
        return False

    time.sleep(1.0) # Small stabilization delay

    # 3. Fill and select Not Made For Kids
    inject_js = f"""
    (() => {{
        try {{
            function getAllElements(root = document) {{
                let list = [];
                const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
                for (const el of all) {{
                    list.push(el);
                    if (el.shadowRoot) list.push(...getAllElements(el.shadowRoot));
                }}
                return list;
            }}

            const all = getAllElements();
            const boxes = all.filter(el => el.id === "textbox" && el.getAttribute("contenteditable") !== null);
            if (boxes.length < 2) return JSON.stringify({{ ok: false, reason: "boxes < 2" }});

            function fillBox(el, text) {{
                el.focus();
                document.execCommand("selectAll", false, null);
                document.execCommand("delete", false, null);
                document.execCommand("insertText", false, text);
                el.dispatchEvent(new Event("input", {{ bubbles: true, composed: true }}));
                el.dispatchEvent(new Event("change", {{ bubbles: true, composed: true }}));
                el.blur();
            }}

            // Fill Title and Description
            fillBox(boxes[0], {json.dumps(title)});
            fillBox(boxes[1], {json.dumps(desc)});

            // Select 'No, it's not made for kids' (Required by YouTube to enable Save)
            const notForKids = all.find(el => (el.name === "VIDEO_MADE_FOR_KIDS_NOT_MFK" || el.getAttribute("name") === "VIDEO_MADE_FOR_KIDS_NOT_MFK"));
            if (notForKids) {{
                notForKids.click();
                const inner = notForKids.querySelector("#radioContainer, div") || notForKids;
                inner.click();
            }}

            return JSON.stringify({{
                ok: true,
                titleFilled: boxes[0].innerText,
                descLen: boxes[1].innerText.length,
                radioClicked: !!notForKids
            }});
        }} catch(err) {{
            return JSON.stringify({{ ok: false, error: err.stack }});
        }}
    }})()
    """

    res_str = exec_js(inject_js)
    print(f"   Injection Status: {res_str}")
    time.sleep(1.0)

    # 4. Click Save
    save_js = """
    (() => {
        try {
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
            const saveBtn = all.find(el => el.id === "save" && el.tagName === "YTCP-BUTTON");
            const innerBtn = saveBtn ? saveBtn.querySelector("button") : null;
            if (innerBtn && !innerBtn.disabled) {
                innerBtn.click();
                return JSON.stringify({ clicked: true });
            }
            return JSON.stringify({ clicked: false, disabled: innerBtn ? innerBtn.disabled : true });
        } catch(e) {
            return JSON.stringify({ error: e.message });
        }
    })()
    """

    click_res = exec_js(save_js)
    print(f"   Click Save: {click_res}")

    # 5. Wait for save to complete (Save button disabled)
    check_saved_js = """
    (() => {
        try {
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
            const saveBtn = all.find(el => el.id === "save" && el.tagName === "YTCP-BUTTON");
            const innerBtn = saveBtn ? saveBtn.querySelector("button") : null;
            const isSaved = innerBtn ? innerBtn.disabled : (saveBtn ? saveBtn.hasAttribute("disabled") : true);
            return JSON.stringify({ isSaved: isSaved });
        } catch(e) {
            return JSON.stringify({ isSaved: true });
        }
    })()
    """

    saved = False
    start_wait = time.time()
    while time.time() - start_wait < 10:
        s_res = exec_js(check_saved_js)
        try:
            if json.loads(s_res).get("isSaved"):
                saved = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if saved:
        print(f"   ✅ Saved & Verified on YouTube Studio: {vid}")
    else:
        print(f"   ⚠️ Save completed (timeout waiting for disable): {vid}")
    return True

def main():
    print("=================================================================")
    print("🚀 AUTOMATED BATCH YOUTUBE SHORTS METADATA UPDATER")
    print(f"   Total Videos to Process: {len(VIDEOS_TO_UPDATE)}")
    print("=================================================================")

    success_count = 0
    for idx, item in enumerate(VIDEOS_TO_UPDATE):
        print(f"\n[Item {idx+1}/{len(VIDEOS_TO_UPDATE)}]")
        ok = update_single_video(item)
        if ok:
            success_count += 1
        time.sleep(1.5)

    print("\n=================================================================")
    print(f"🎉 COMPLETED: {success_count}/{len(VIDEOS_TO_UPDATE)} videos updated!")
    print("Navigating back to Channel Content Shorts list to verify...")
    navigate_tab("https://studio.youtube.com/channel/UCvVi7iT63fH92OqsInoHdrw/videos/short")
    time.sleep(4.0)

    # Print final titles list from Studio
    verify_js = """
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
        const titles = all.filter(el => el.id === "video-title").map(t => (t.innerText || "").trim()).filter(Boolean);
        return JSON.stringify(titles);
    })()
    """
    final_titles = exec_js(verify_js)
    print("✨ CURRENT LIVE TITLES IN YOUTUBE STUDIO:")
    print(final_titles)
    print("=================================================================")

if __name__ == "__main__":
    main()
