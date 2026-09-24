# -*- coding: utf-8 -*-
"""Seeds the four roles and a synthetic network of 5,000 groups, so that the
scale claims in the proposal can actually be exercised rather than asserted."""
import json
import random

from sqlalchemy import select, func

import config
import security
from db import SessionLocal, User, Group, GroupList, GroupListMember, Template

GROUP_TARGET = 5000

CATEGORIES = ["Community", "Trade", "Education", "Health", "Agriculture",
              "Youth", "Women's Collective", "Municipal", "Transport",
              "Emergency Response"]
FOLDERS = ["North Zone", "South Zone", "East Zone", "West Zone", "Central Zone"]
TAGS = ["priority", "weekly-digest", "high-engagement", "regional", "pilot",
        "verified", "low-volume", "media-heavy", "multilingual"]
REGIONS = ["Haryana", "Punjab", "Delhi NCR", "Himachal Pradesh", "Rajasthan",
           "Uttar Pradesh", "Chandigarh", "Uttarakhand"]
PLACES = ["Panchkula", "Ambala", "Karnal", "Hisar", "Rohtak", "Sonipat",
          "Ludhiana", "Amritsar", "Patiala", "Jalandhar", "Shimla", "Solan",
          "Jaipur", "Kota", "Agra", "Meerut", "Dehradun", "Haridwar",
          "Gurugram", "Faridabad", "Noida", "Bhiwani", "Sirsa", "Yamunanagar"]
UNITS = ["Ward", "Block", "Sector", "Circle", "Unit", "Chapter", "Cell",
         "Forum", "Network", "Council"]

SEED_USERS = [
    ("admin@gsuretech.com", "Platform Administrator", "SUPER_ADMIN", "Gsure@2026"),
    ("manager@gsuretech.com", "Campaign Manager", "CAMPAIGN_MANAGER", "Gsure@2026"),
    ("analyst@gsuretech.com", "Reporting Analyst", "ANALYST", "Gsure@2026"),
    ("viewer@gsuretech.com", "Read Only Viewer", "VIEWER", "Gsure@2026"),
]

TEMPLATES = [
    ("Weekly community bulletin",
     "Namaste {{group_name}},\n\nThis week's bulletin is now available. It "
     "covers scheme updates, helpline timings and the schedule for the coming "
     "week.\n\nRead the full bulletin here: {{link}}\n\nRegards,\nCommunications Office"),
    ("Service advisory",
     "Attention {{group_name}}\n\nA scheduled service interruption is planned. "
     "Please review the advisory and share it within your group.\n\n{{link}}"),
    ("Event invitation",
     "Dear members of {{group_name}},\n\nYou are invited to the forthcoming "
     "session. Registration and the agenda are available at the link "
     "below.\n\n{{link}}\n\nKindly register in advance as seating is limited."),
]


DIRECT_TEMPLATES = [
    ("Interview reminder",
     "Hello {{name}},\n\nThis is a reminder of your interview scheduled for tomorrow. "
     "Please reply to confirm you will attend, or let us know if you need to reschedule.\n\n"
     "Thank you."),
    ("Follow-up",
     "Hello {{name}},\n\nFollowing up on our earlier message. Please reply here if you "
     "have any questions and we will get back to you."),
]


def ensure_seed():
    with SessionLocal() as s:
        if s.scalar(select(func.count()).select_from(User)) == 0:
            for email, name, role, pwd in SEED_USERS:
                s.add(User(email=email, name=name, role=role,
                           password_hash=security.hash_password(pwd)))
            s.commit()
            print(f"  Seeded {len(SEED_USERS)} users (password Gsure@2026)")

        existing = s.scalar(select(func.count()).select_from(Group)) or 0
        if existing < GROUP_TARGET:
            rng = random.Random(20260919)
            batch = []
            for i in range(existing, GROUP_TARGET):
                place = rng.choice(PLACES)
                unit = rng.choice(UNITS)
                cat = rng.choice(CATEGORIES)
                name = f"{place} {unit} {rng.randint(1, 60)} - {cat}"
                tags = rng.sample(TAGS, rng.randint(1, 3))
                batch.append(Group(
                    wa_group_id=f"{rng.randint(10**11, 10**12 - 1)}@g.us",
                    name=name, category=cat, folder=rng.choice(FOLDERS),
                    tags_json=json.dumps(tags),
                    member_count=rng.randint(24, 1024),
                    region=rng.choice(REGIONS), source="seed",
                    active=rng.random() > 0.04))
                if len(batch) >= 500:
                    s.add_all(batch)
                    s.commit()
                    batch = []
            if batch:
                s.add_all(batch)
                s.commit()
            print(f"  Seeded {GROUP_TARGET - existing} groups "
                  f"(total {GROUP_TARGET})")

        if s.scalar(select(func.count()).select_from(Template)) == 0:
            for name, body in TEMPLATES:
                s.add(Template(name=name, body=body))
            s.commit()

        # Templates suited to one to one and group messages. {{name}} is the
        # recipient's name, {{group_name}} the group's. Added only if missing.
        for name, body in DIRECT_TEMPLATES:
            if not s.scalar(select(Template).where(Template.name == name)):
                s.add(Template(name=name, body=body))
        s.commit()

        if s.scalar(select(func.count()).select_from(GroupList)) == 0:
            for list_name, where in (
                    ("Priority groups", lambda g: "priority" in g.tags),
                    ("North Zone weekly", lambda g: g.folder == "North Zone"),
                    ("Emergency response network",
                     lambda g: g.category == "Emergency Response")):
                gl = GroupList(name=list_name,
                               description="Seeded example campaign list")
                s.add(gl)
                s.flush()
                members = [g.id for g in s.scalars(select(Group)) if where(g)][:900]
                for gid in members:
                    s.add(GroupListMember(list_id=gl.id, group_id=gid))
            s.commit()
            print("  Seeded 3 saved campaign lists")


if __name__ == "__main__":
    from db import init_db
    init_db()
    ensure_seed()
    print("Seed complete.")
