#!/usr/bin/env python3
import json
import os

# Read catalog
with open('catalog/catalog.json', 'r') as f:
    catalog = json.load(f)

# Read candidates
with open('candidates.json', 'r') as f:
    candidates = json.load(f)

# Build offer lookup by offerId
offer_lookup = {offer['offerId']: offer for offer in catalog['offers']}

# Check images directory for each offer
images_base = 'catalog/images'
for offer_id in offer_lookup:
    offer_dir = os.path.join(images_base, offer_id)
    if os.path.exists(offer_dir):
        files = os.listdir(offer_dir)
        print(f"{offer_id}: {files}")
    else:
        print(f"{offer_id}: no image folder")