#!/usr/bin/env python3
"""
move-images.py — Move images from GitHub root to public/ and public/footer/
Run: python3 move-images.py YOUR_GITHUB_TOKEN
"""
import sys, json, time, urllib.request, urllib.error, base64

REPO = "rishavbuilder/yaso-anime-backend"
BRANCH = "main"

if len(sys.argv) < 2:
    print("Usage: python3 move-images.py <GITHUB_TOKEN>")
    sys.exit(1)

TOKEN = sys.argv[1]
API = f"https://api.github.com/repos/{REPO}"

def api_call(method, path, data=None):
    url = f"{API}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"    ERROR {e.code}: {err.get('message', str(err))}")
        return None

print("=== Step 1: Fetching root tree ===")
ref_data = api_call("GET", f"/git/ref/heads/{BRANCH}")
tree_sha = ref_data["object"]["sha"]
print(f"Tree SHA: {tree_sha}")

tree_data = api_call("GET", f"/git/trees/{tree_sha}?recursive=1")
root_images = [(item["path"], item["sha"]) for item in tree_data.get("tree", [])
               if "/" not in item["path"] and item["path"].endswith(('.jpg', '.png', '.svg', '.ico'))]

print(f"Root images found: {[x[0] for x in root_images]}")

print("\n=== Step 2: Downloading root images ===")
import tempfile, os
tmpdir = tempfile.mkdtemp()

for filename, sha in root_images:
    print(f"  Downloading: {filename}")
    url = f"{API}/contents/{filename}?ref={BRANCH}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3.raw")
    with urllib.request.urlopen(req) as resp:
        with open(os.path.join(tmpdir, filename), "wb") as f:
            f.write(resp.read())

print("\n=== Step 3: Uploading to public/ ===")
hero_images = ["journey-through-bamboo-forest.jpg", "c1e4a8b37dccb95eca2b645f7f3473f2.jpg"]

for img in hero_images:
    filepath = os.path.join(tmpdir, img)
    if not os.path.exists(filepath):
        print(f"  SKIP: {img}")
        continue
    print(f"  Uploading: public/{img}")
    with open(filepath, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()
    result = api_call("PUT", f"/contents/public/{img}", {
        "message": f"Move {img} to public/",
        "content": content_b64,
        "branch": BRANCH
    })
    print(f"    {'OK' if result and 'content' in result else 'FAILED'}")
    time.sleep(0.5)

print("\n=== Step 4: Uploading to public/footer/ ===")
footer_images = ["footer-bw.jpg", "footer-dark.jpg", "footer-horns.jpg",
                 "footer-moto.jpg", "footer-pink.jpg", "footer-room.jpg", "footer-ruins.jpg"]

for img in footer_images:
    filepath = os.path.join(tmpdir, img)
    if not os.path.exists(filepath):
        print(f"  SKIP: {img}")
        continue
    print(f"  Uploading: public/footer/{img}")
    with open(filepath, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()
    result = api_call("PUT", f"/contents/public/footer/{img}", {
        "message": f"Move {img} to public/footer/",
        "content": content_b64,
        "branch": BRANCH
    })
    print(f"    {'OK' if result and 'content' in result else 'FAILED'}")
    time.sleep(0.5)

print("\n=== Step 5: Deleting from root ===")
all_images = hero_images + footer_images
image_shas = {name: sha for name, sha in root_images}

for img in all_images:
    if img not in image_shas:
        continue
    print(f"  Deleting root: {img}")
    result = api_call("DELETE", f"/contents/{img}", {
        "message": f"Remove {img} from root (moved to public/)",
        "sha": image_shas[img],
        "branch": BRANCH
    })
    print(f"    {'OK' if result else 'FAILED'}")
    time.sleep(0.5)

print("\n=== Step 6: Verifying ===")

print("\npublic/ contents:")
for item in api_call("GET", f"/contents/public?ref={BRANCH}") or []:
    print(f"  {item['name']} ({item.get('type', '?')})")

print("\npublic/footer/ contents:")
for item in api_call("GET", f"/contents/public/footer?ref={BRANCH}") or []:
    print(f"  {item['name']} ({item.get('type', '?')})")

print("\nRoot level images:")
root_contents = api_call("GET", f"/contents?ref={BRANCH}") or []
stray = [item for item in root_contents if item["name"].endswith(('.jpg', '.png', '.svg', '.ico'))]
if stray:
    for item in stray:
        print(f"  STRAY: {item['name']}")
else:
    print("  None (all moved)")

print("\n=== DONE ===")
print("Next: Go to Render dashboard -> Manual Deploy -> Clear build cache & deploy")
