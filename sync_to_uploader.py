import os
import json
import shutil
import subprocess
from pathlib import Path

GTA_DIR = Path("/Users/deepanshumohan/Work/gta")
TO_BE_UPLOADED_DIR = GTA_DIR / "to_be_uploaded"
UPLOADER_DIR = Path("/Users/deepanshumohan/Work/gta_uploader")
REELS_OUTPUT_DIR = UPLOADER_DIR / "output" / "reels"
CONTENT_REELS_FILE = UPLOADER_DIR / "content" / "reels.json"
BRAND_SETTINGS_FILE = UPLOADER_DIR / "brand_settings.json"

REELS_CONFIG = [
    {
        "file_prefix": "01_Can_You_Stop_The_Train_In_GTA6",
        "reel_id": "woldo-gta6-01-train-stop",
        "title": "CAN YOU FINALLY STOP THE TRAIN?!",
        "post_caption": "CAN YOU FINALLY STOP THE GTA 6 TRAIN?! In GTA 5 the train was literally indestructible, but in GTA 6 next-gen physics allow real collisions and emergency stops! Watch the high-speed impact!",
        "tags": ["#GTA6", "#GTAMyths", "#GamingMythbusters", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 30
    },
    {
        "file_prefix": "02_GTA6_Police_Logic_Makes_Zero_Sense",
        "reel_id": "woldo-gta6-02-police-logic",
        "title": "GTA 6 POLICE LOGIC MAKES ZERO SENSE!",
        "post_caption": "GTA 6 POLICE LOGIC MAKES ZERO SENSE! You accidentally bump an officer and suddenly five SWAT cruisers spawn behind you! Vice City PD does not play around!",
        "tags": ["#GTA6", "#ViceCityPD", "#PoliceLogic", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 30
    },
    {
        "file_prefix": "03_GTA6_NextGen_Car_Damage_Physics",
        "reel_id": "woldo-gta6-03-car-damage",
        "title": "GTA 6 NEXT-GEN CAR DAMAGE IS INSANE!",
        "post_caption": "TESTING NEXT-GEN CAR DAMAGE IN GTA 6! Dynamic crumple zones, frame twisting, and wheel detachment at 150+ MPH! Rockstar went full simulation mode!",
        "tags": ["#GTA6", "#CarDamage", "#GamingPhysics", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 25
    },
    {
        "file_prefix": "04_Driving_Across_The_Entire_GTA6_Map",
        "reel_id": "woldo-gta6-04-map-drive",
        "title": "DRIVING ACROSS THE ENTIRE GTA 6 MAP!",
        "post_caption": "DRIVING ACROSS THE ENTIRE GTA 6 MAP AT 220 MPH! Starting from Downtown Vice City all the way through neon boulevards and ocean highways! Leonida is 2.5x bigger than Los Santos!",
        "tags": ["#GTA6", "#GTA6Map", "#ViceCity", "#Supercars", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 30
    },
    {
        "file_prefix": "05_GTA6_Damage_Physics_Item_Tier_List",
        "reel_id": "woldo-gta6-05-damage-tier-list",
        "title": "GTA 6 DAMAGE PHYSICS ITEM TIER LIST!",
        "post_caption": "GTA 6 DAMAGE PHYSICS TIER LIST! Ranking vehicle destruction from B-Tier to God-Tier! Watch how supercars crumple vs heavy trucks! Do you agree with this ranking?",
        "tags": ["#GTA6", "#TierList", "#DamagePhysics", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 30
    },
    {
        "file_prefix": "06_GTA6_In_Game_TikTok_Doomscrolling",
        "reel_id": "woldo-gta6-06-tiktok-doomscroll",
        "title": "GTA 6 IN-GAME TIKTOK DOOMSCROLLING!",
        "post_caption": "GTA 6 ADDED IN-GAME TIKTOK AND DOOMSCROLLING! Unhinged Vice City social media posts, live stream comments, alligator pool rescues, and viral memes! Rockstar's satire is unmatched!",
        "tags": ["#GTA6", "#GTA6TikTok", "#Doomscrolling", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 18
    },
    {
        "file_prefix": "01_Speed_Craziest_GTA6_Cop_Chase",
        "reel_id": "woldo-gta6-07-speed-cop-chase",
        "title": "SPEED'S CRAZIEST GTA 6 COP CHASE!",
        "post_caption": "SPEED GETS 5 STARS IN GTA 6! Complete chaos as Speed flips his car across the Vice City highway while screaming at the cops! Peak Speed energy!",
        "tags": ["#IShowSpeed", "#GTA6", "#SpeedClips", "#CopChase", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 26
    },
    {
        "file_prefix": "01_Techno_Gamerz_First_Day_In_Vice_City",
        "reel_id": "woldo-gta6-08-techno-gamerz",
        "title": "TECHNO GAMERZ FIRST DAY IN VICE CITY!",
        "post_caption": "TECHNO GAMERZ FIRST DAY IN GTA 6! Ujjwal steals his first supercar and checks out next-gen Vice City graphics and sound! Pure gaming hype!",
        "tags": ["#TechnoGamerz", "#GTA6", "#ViceCity", "#GamingIndia", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 28
    },
    {
        "file_prefix": "01_Mythpat_Mindblown_By_GTA6",
        "reel_id": "woldo-gta6-09-mythpat-reaction",
        "title": "MYTHPAT REACTS TO GTA 6!",
        "post_caption": "MYTHPAT REACTS TO GTA 6 FOR THE FIRST TIME! Dimaag hila diya! Mythpat could not believe the graphics, pedestrian physics, and Vice City world scale!",
        "tags": ["#Mythpat", "#GTA6", "#GamingReactions", "#GamingIndia", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 28
    },
    {
        "file_prefix": "01_Jynxzi_Best_GTA6_Moments",
        "reel_id": "woldo-gta6-10-jynxzi-moments",
        "title": "JYNXZI CRAZIEST GTA 6 MOMENT!",
        "post_caption": "JYNXZI CANNOT HANDLE GTA 6! Four-star panic flying over Vice City, military jargon, and unfiltered Jynxzi screams! Pure comedy gold!",
        "tags": ["#Jynxzi", "#GTA6", "#JynxziClips", "#GamingMoments", "#WoldoPlays", "#Gaming", "#Shorts", "#Reels"],
        "duration": 26
    }
]

def main():
    print("🚀 Syncing 10 GTA 6 Reels into gta_uploader for WoldoPlays...")
    REELS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Update brand_settings.json
    brand = {
        "name": "WoldoPlays",
        "handle": "@WoldoPlays",
        "youtubeUrl": "https://www.youtube.com/@WoldoPlays",
        "instagramUrl": "https://www.instagram.com/woldoplays/",
        "colors": {
            "primary": "#FFCC00",
            "accent": "#FF0000",
            "background": "#0F172A",
            "white": "#FFFFFF"
        }
    }
    with open(BRAND_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(brand, f, indent=2)
    print("✅ Updated brand_settings.json for WoldoPlays")

    # 2. Process each reel
    reels_manifest = []
    
    for item in REELS_CONFIG:
        reel_id = item["reel_id"]
        target_dir = REELS_OUTPUT_DIR / reel_id
        target_dir.mkdir(parents=True, exist_ok=True)
        
        src_mp4 = TO_BE_UPLOADED_DIR / f"{item['file_prefix']}.mp4"
        src_ass = TO_BE_UPLOADED_DIR / f"{item['file_prefix']}.ass"
        
        dest_mp4 = target_dir / f"{reel_id}.mp4"
        dest_ass = target_dir / f"{reel_id}.ass"
        
        if src_mp4.exists():
            shutil.copy2(src_mp4, dest_mp4)
            print(f"📦 Copied {src_mp4.name} -> {dest_mp4.relative_to(UPLOADER_DIR)}")
        else:
            print(f"❌ Missing source MP4: {src_mp4}")
            continue
            
        if src_ass.exists():
            shutil.copy2(src_ass, dest_ass)
            
        # Extract thumbnail poster
        thumb_jpg = target_dir / "thumbnail.jpg"
        cover_png = target_dir / "frame_01_cover.png"
        subprocess.run([
            "ffmpeg", "-y", "-ss", "00:00:01.5", "-i", str(dest_mp4),
            "-vframes", "1", "-q:v", "2", str(thumb_jpg)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if thumb_jpg.exists():
            shutil.copy2(thumb_jpg, cover_png)
            
        # Write Captions
        title = item["title"]
        post_caption = item["post_caption"]
        tags_str = " ".join(item["tags"])
        
        yt_caption = f"{title} #Shorts\n\n{post_caption}\n\n🔔 Subscribe to @WoldoPlays for daily GTA 6 clips, myths & insane moments!\n\n{tags_str}"
        ig_caption = f"{title}\n\n{post_caption}\n\n🔥 Follow @woldoplays for daily GTA 6 gameplay & viral moments!\n.\n.\n{tags_str}"
        generic_caption = f"{title}\n\n{post_caption}\n\n{tags_str}"
        
        with open(target_dir / "caption.txt", "w", encoding="utf-8") as f:
            f.write(generic_caption)
        with open(target_dir / "caption.youtube.txt", "w", encoding="utf-8") as f:
            f.write(yt_caption)
        with open(target_dir / "caption.instagram.txt", "w", encoding="utf-8") as f:
            f.write(ig_caption)
            
        captions_json = {
            "id": reel_id,
            "title": title,
            "variants": {
                "instagram": [
                    {"angle": "curiosity", "caption": ig_caption},
                    {"angle": "hook", "caption": f"{title}\n\n{tags_str}"}
                ],
                "youtube": [
                    {"angle": "curiosity", "caption": yt_caption},
                    {"angle": "hook", "caption": f"{title} #Shorts\n\n{post_caption}"}
                ]
            }
        }
        with open(target_dir / "captions.json", "w", encoding="utf-8") as f:
            json.dump(captions_json, f, indent=2)
            
        reels_manifest.append({
            "id": reel_id,
            "title": title,
            "source_file": item["file_prefix"],
            "type": "video-clip",
            "duration": item["duration"],
            "theme": "gta6-viral",
            "audience": ["gaming", "gta6", "viral"],
            "captions": {
                "hook": title,
                "body": post_caption,
                "youtube": yt_caption,
                "instagram": ig_caption
            }
        })
        
    # Update reels.json
    with open(CONTENT_REELS_FILE, "w", encoding="utf-8") as f:
        json.dump(reels_manifest, f, indent=2)
    print(f"🎉 Updated {CONTENT_REELS_FILE} with {len(reels_manifest)} reels.")
    print("✨ Sync complete! All 10 reels prepared for @WoldoPlays.")

if __name__ == "__main__":
    main()

