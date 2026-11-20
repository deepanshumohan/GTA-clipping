import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

GTA_DIR = Path("/Users/deepanshumohan/Work/gta")
TO_BE_UPLOADED_DIR = GTA_DIR / "to_be_uploaded"
UPLOADED_DIR = GTA_DIR / "uploaded"
UPLOADER_DIR = Path("/Users/deepanshumohan/Work/gta_uploader")
PUB_LOG_FILE = UPLOADED_DIR / "publication_manifest.json"

UPLOAD_QUEUE = [
    {
        "source_name": "01_Can_You_Stop_The_Train_In_GTA6",
        "reel_id": "woldo-gta6-01-train-stop",
        "title": "CAN YOU FINALLY STOP THE TRAIN?!"
    },
    {
        "source_name": "02_GTA6_Police_Logic_Makes_Zero_Sense",
        "reel_id": "woldo-gta6-02-police-logic",
        "title": "GTA 6 POLICE LOGIC MAKES ZERO SENSE!"
    },
    {
        "source_name": "03_GTA6_NextGen_Car_Damage_Physics",
        "reel_id": "woldo-gta6-03-car-damage",
        "title": "GTA 6 NEXT-GEN CAR DAMAGE IS INSANE!"
    },
    {
        "source_name": "04_Driving_Across_The_Entire_GTA6_Map",
        "reel_id": "woldo-gta6-04-map-drive",
        "title": "DRIVING ACROSS THE ENTIRE GTA 6 MAP!"
    },
    {
        "source_name": "05_GTA6_Damage_Physics_Item_Tier_List",
        "reel_id": "woldo-gta6-05-damage-tier-list",
        "title": "GTA 6 DAMAGE PHYSICS ITEM TIER LIST!"
    },
    {
        "source_name": "06_GTA6_In_Game_TikTok_Doomscrolling",
        "reel_id": "woldo-gta6-06-tiktok-doomscroll",
        "title": "GTA 6 IN-GAME TIKTOK DOOMSCROLLING!"
    },
    {
        "source_name": "01_Speed_Craziest_GTA6_Cop_Chase",
        "reel_id": "woldo-gta6-07-speed-cop-chase",
        "title": "SPEED'S CRAZIEST GTA 6 COP CHASE!"
    },
    {
        "source_name": "01_Techno_Gamerz_First_Day_In_Vice_City",
        "reel_id": "woldo-gta6-08-techno-gamerz",
        "title": "TECHNO GAMERZ FIRST DAY IN VICE CITY!"
    },
    {
        "source_name": "01_Mythpat_Mindblown_By_GTA6",
        "reel_id": "woldo-gta6-09-mythpat-reaction",
        "title": "MYTHPAT REACTS TO GTA 6!"
    },
    {
        "source_name": "01_Jynxzi_Best_GTA6_Moments",
        "reel_id": "woldo-gta6-10-jynxzi-moments",
        "title": "JYNXZI CRAZIEST GTA 6 MOMENT!"
    }
]

def load_pub_manifest():
    if PUB_LOG_FILE.exists():
        try:
            with open(PUB_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"uploads": []}
    return {"uploads": []}

def save_pub_manifest(data):
    UPLOADED_DIR.mkdir(parents=True, exist_ok=True)
    with open(PUB_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def move_to_uploaded(source_name):
    UPLOADED_DIR.mkdir(parents=True, exist_ok=True)
    moved = []
    for ext in [".mp4", ".ass", ".scorecard.json"]:
        src = TO_BE_UPLOADED_DIR / f"{source_name}{ext}"
        dst = UPLOADED_DIR / f"{source_name}{ext}"
        if src.exists():
            shutil.move(str(src), str(dst))
            moved.append(dst.name)
    print(f"📦 Moved to uploaded/: {', '.join(moved)}")
    return moved

def run_platform_upload(platform, reel_id):
    script = f"post-{platform}.js"
    cmd = ["node", script, "reel", reel_id]
    print(f"🚀 Publishing {reel_id} to {platform.upper()}...")
    proc = subprocess.run(cmd, cwd=str(UPLOADER_DIR), capture_output=True, text=True)
    print(proc.stdout)
    if proc.stderr:
        print(f"stderr: {proc.stderr}")
    return proc.returncode == 0

def upload_single_reel(item, target_platform="all"):
    reel_id = item["reel_id"]
    source_name = item["source_name"]
    print(f"\n{'='*60}")
    print(f"Processing Reel: {item['title']} ({reel_id})")
    print(f"{'='*60}")

    manifest = load_pub_manifest()
    record = next((u for u in manifest["uploads"] if u["reel_id"] == reel_id), None)
    if not record:
        record = {
            "reel_id": reel_id,
            "source_name": source_name,
            "title": item["title"],
            "youtube": False,
            "instagram": False
        }
        manifest["uploads"].append(record)

    yt_ok = record["youtube"]
    ig_ok = record["instagram"]

    if target_platform in ("youtube", "all") and not yt_ok:
        yt_ok = run_platform_upload("youtube", reel_id)
        record["youtube"] = yt_ok

    if target_platform in ("instagram", "all") and not ig_ok:
        ig_ok = run_platform_upload("instagram", reel_id)
        record["instagram"] = ig_ok

    save_pub_manifest(manifest)

    # If completed on requested platforms, move from to_be_uploaded to uploaded
    if (target_platform == "all" and yt_ok and ig_ok) or \
       (target_platform == "youtube" and yt_ok) or \
       (target_platform == "instagram" and ig_ok):
        move_to_uploaded(source_name)
        print(f"✅ Reel {reel_id} successfully uploaded and moved to uploaded/ folder!")

if __name__ == "__main__":
    platform = sys.argv[1] if len(sys.argv) > 1 else "all"
    target_id = sys.argv[2] if len(sys.argv) > 2 else None

    for item in UPLOAD_QUEUE:
        if target_id and item["reel_id"] != target_id and item["source_name"] != target_id:
            continue
        upload_single_reel(item, target_platform=platform)

