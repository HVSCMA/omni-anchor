"""
Optimized Stateful Database Export Utility
Leverages quick sequential loops to pull, compile, and stream.
"""
import httpx
import base64
import json
import csv
import sys
from datetime import datetime, timezone

FUB_API_KEY = "fka_0oHt627BvH4oOoy10aILIRiLBTnknLrilU"
_creds = base64.b64encode(f"{FUB_API_KEY}:".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_creds}",
    "Content-Type": "application/json",
    "X-System": "OMNI-ANCHOR",
    "X-System-Key": "f1e0c6af664bc1525ecd8fecba255235"
}

def export():
    contacts = []
    url = "https://api.followupboss.com/v1/people"
    params = {"limit": 100}
    
    print("Beginning FUB paginated export...", flush=True)
    with httpx.Client() as client:
        while url:
            r = client.get(url, headers=HEADERS, params=params, timeout=30.0)
            if r.status_code == 429:
                import time
                time.sleep(5)
                continue
            r.raise_for_status()
            data = r.json()
            batch = data.get("people", [])
            if not batch:
                break
            contacts.extend(batch)
            print(f"Retrieved: {len(contacts)} records...", flush=True)
            
            # Follow Up Boss cursor pagination
            meta = data.get("_metadata", {})
            url = meta.get("nextLink")
            params = None # Query parameters are baked in nextLink
            
    # Compile CSV
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = f"/root/omni-anchor/backups/fub_export_{timestamp}.csv"
    
    headers = [
        "id", "name", "firstName", "lastName", "stage", "stageId", 
        "emails", "phones", "tags", "created", "updated"
    ]
    
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for c in contacts:
            emails = "; ".join([e.get("value", "") for e in c.get("emails", [])])
            phones = "; ".join([p.get("value", "") for p in c.get("phones", [])])
            tags = ", ".join(c.get("tags", []))
            writer.writerow([
                c.get("id"),
                c.get("name"),
                c.get("firstName"),
                c.get("lastName"),
                c.get("stage"),
                c.get("stageId"),
                emails,
                phones,
                tags,
                c.get("created"),
                c.get("updated")
            ])
            
    print(f"SUCCESS: Compiled {len(contacts)} contacts to {out_path}", flush=True)

if __name__ == "__main__":
    export()
