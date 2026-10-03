#!/usr/bin/env python3
import json, urllib.request, readline

print("Joern REPL → localhost:8080  (Ctrl+C to exit)\n")
while True:
    try:
        query = input("joern> ").strip()
        if not query:
            continue
        req = urllib.request.Request(
            "http://localhost:8080/query-sync",
            data=json.dumps({"query": query}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
            print(d.get("stdout", "").strip())
            if d.get("stderr"):
                print("[err]:", d["stderr"][:500])
    except KeyboardInterrupt:
        print("\nBye")
        break
