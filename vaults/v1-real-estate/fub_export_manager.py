"""
Follow Up Boss Database Exporter — OMNI-ANCHOR v4.3
Establishes a paginated extraction process across the active Follow Up Boss database.
Compiles all contacts and custom fields into a structured CSV archive file.

Target Count: ~1,599 records
File Path   : /root/omni-anchor/backups/fub_export_[timestamp].csv
"""
import os
import sys
import json
import csv
import asyncio
from datetime import datetime, timezone
import httpx

# Resolve import paths to include vaults
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import fub_client

# Define outputs
EXPORT_DIR = "/root/omni-anchor/backups"
os.makedirs(EXPORT_DIR, exist_ok=True)

def utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

async def run_database_export() -> str:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Initiating paginated database extraction...")
    
    # 1. Fetch entire user map for resolution
    users = fub_client.USERS
    
    # 2. Extract paginated results using FUB basic auth and X-System blocks
    path = "/people"
    params = {
        "limit": 100,
        "offset": 0
    }
    
    all_contacts = []
    cursor = None
    
    while True:
        if cursor:
            params["next"] = cursor
        
        # Build raw request to match basic clients directly with our non-rate-limited standard headers
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{fub_client.FUB_BASE}{path}",
                headers=fub_client.HEADERS,
                params=params if not cursor else None,  # FUB nextLink has query params
                timeout=30
            )
        
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 5))
            print(f"  Rate limited. Sleeping for {retry_after} seconds...")
            await asyncio.sleep(retry_after)
            continue
            
        r.raise_for_status()
        data = r.json()
        
        contacts = data.get("people", [])
        if not contacts:
            break
            
        all_contacts.extend(contacts)
        print(f"  Extracted {len(all_contacts)} contacts...")
        
        meta = data.get("_metadata", {})
        cursor = meta.get("next")
        if not cursor or len(contacts) == 0:
            break
            
        # Standard loop defensive pacing to prevent spiking
        await asyncio.sleep(0.1)

    print(f"[{datetime.now(timezone.utc).isoformat()}] Fetch complete. Total retrieved: {len(all_contacts)}")
    
    # 3. Flatten and compile records
    timestamp = utcnow_str()
    csv_file = os.path.join(EXPORT_DIR, f"fub_export_{timestamp}.csv")
    
    # Extract headers headers
    headers = [
        "id", "name", "firstName", "lastName", "stage", "stageId", "type", 
        "source", "sourceUrl", "created", "updated", "lastActivity", 
        "assignedTo", "assignedUserId", "price", "emails", "phones", "tags"
    ]
    
    # Appending custom fields
    custom_field_keys = list(fub_client.CUSTOM_FIELDS.keys())
    headers.extend(custom_field_keys)
    
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for c in all_contacts:
            # Flatten standard fields
            emails = ", ".join([e.get("value", "") for e in c.get("emails", [])])
            phones = ", ".join([p.get("value", "") for p in c.get("phones", [])])
            tags = ", ".join(c.get("tags", []))
            
            row = [
                c.get("id"),
                c.get("name"),
                c.get("firstName"),
                c.get("lastName"),
                c.get("stage"),
                c.get("stageId"),
                c.get("type"),
                c.get("source"),
                c.get("sourceUrl"),
                c.get("created"),
                c.get("updated"),
                c.get("lastActivity"),
                c.get("assignedTo"),
                c.get("assignedUserId"),
                c.get("price"),
                emails,
                phones,
                tags
            ]
            
            # Extract custom field parameters if matched directly to client dictionary mappings
            for cf in custom_field_keys:
                row.append(c.get(cf, ""))
                
            writer.writerow(row)
            
    print(f"[{datetime.now(timezone.utc).isoformat()}] Database exported and compiled to: {csv_file}")
    return csv_file

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        asyncio.run(run_database_export())
