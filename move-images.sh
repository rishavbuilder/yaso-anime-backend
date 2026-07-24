#!/bin/bash
set -e

# =====================================================
# move-images.sh
# Downloads images from GitHub root, moves to correct
# paths (public/ and public/footer/), deletes from root.
# =====================================================

REPO="rishavbuilder/yaso-anime-backend"
BRANCH="main"

# --- Ask for token ---
if [ -z "$GITHUB_TOKEN" ]; then
  read -rp "GitHub Personal Access Token: " GITHUB_TOKEN
fi

if [ -z "$GITHUB_TOKEN" ]; then
  echo "Error: No token provided."
  exit 1
fi

API="https://api.github.com/repos/$REPO"
AUTH="Authorization: token $GITHUB_TOKEN"

echo ""
echo "=== Step 1: Fetching root tree ==="

# Get the tree SHA of main branch
TREE_SHA=$(curl -s -H "$AUTH" "$API/git/ref/heads/$BRANCH" | python3 -c "import sys,json; print(json.load(sys.stdin)['object']['sha'])")
echo "Tree SHA: $TREE_SHA"

# Get root tree (recursive)
ROOT_TREE=$(curl -s -H "$AUTH" "$API/git/trees/$TREE_SHA?recursive=1")

# Extract files at root level that are images
ROOT_IMAGES=$(echo "$ROOT_TREE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('tree', []):
    if '/' not in item['path'] and item['path'].endswith(('.jpg', '.png', '.svg', '.ico')):
        print(item['path'], item['sha'])
")
echo ""
echo "Root images found:"
echo "$ROOT_IMAGES"

echo ""
echo "=== Step 2: Downloading root images to temp ==="

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

while IFS=' ' read -r filename sha; do
  [ -z "$filename" ] && continue
  echo "  Downloading: $filename"
  curl -sL "$API/contents/$filename?ref=$BRANCH" \
    -H "$AUTH" \
    -H "Accept: application/vnd.github.v3.raw" \
    -o "$TMPDIR/$filename"
done <<< "$ROOT_IMAGES"

echo ""
echo "=== Step 3: Uploading to public/ (hero bg + favicons) ==="

HERO_IMAGES="journey-through-bamboo-forest.jpg c1e4a8b37dccb95eca2b645f7f3473f2.jpg"

for img in $HERO_IMAGES; do
  [ ! -f "$TMPDIR/$img" ] && echo "  SKIP (not found): $img" && continue
  echo "  Uploading: public/$img"
  CONTENT_B64=$(base64 -w0 "$TMPDIR/$img")
  curl -s -X PUT "$API/contents/public/$img" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "{
      \"message\": \"Move $img to public/\",
      \"content\": \"$CONTENT_B64\",
      \"branch\": \"$BRANCH\"
    }" | python3 -c "import sys,json; r=json.load(sys.stdin); print('    OK' if 'content' in r else '    ERROR: '+str(r.get('message','unknown')))"
  sleep 0.5
done

echo ""
echo "=== Step 4: Uploading to public/footer/ ==="

FOOTER_IMAGES="footer-bw.jpg footer-dark.jpg footer-horns.jpg footer-moto.jpg footer-pink.jpg footer-room.jpg footer-ruins.jpg"

for img in $FOOTER_IMAGES; do
  [ ! -f "$TMPDIR/$img" ] && echo "  SKIP (not found): $img" && continue
  echo "  Uploading: public/footer/$img"
  CONTENT_B64=$(base64 -w0 "$TMPDIR/$img")
  curl -s -X PUT "$API/contents/public/footer/$img" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "{
      \"message\": \"Move $img to public/footer/\",
      \"content\": \"$CONTENT_B64\",
      \"branch\": \"$BRANCH\"
    }" | python3 -c "import sys,json; r=json.load(sys.stdin); print('    OK' if 'content' in r else '    ERROR: '+str(r.get('message','unknown')))"
  sleep 0.5
done

echo ""
echo "=== Step 5: Deleting images from root ==="

ALL_IMAGES="$HERO_IMAGES $FOOTER_IMAGES"

for img in $ALL_IMAGES; do
  [ ! -f "$TMPDIR/$img" ] && continue
  echo "  Deleting root: $img"
  # Get SHA from git tree
  FILE_SHA=$(echo "$ROOT_TREE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('tree', []):
    if item['path'] == '$img':
        print(item['sha'])
        break
")
  if [ -n "$FILE_SHA" ]; then
    curl -s -X DELETE "$API/contents/$img" \
      -H "$AUTH" \
      -H "Content-Type: application/json" \
      -d "{
        \"message\": \"Remove $img from root (moved to public/)\",
        \"sha\": \"$FILE_SHA\",
        \"branch\": \"$BRANCH\"
      }" | python3 -c "import sys,json; r=json.load(sys.stdin); print('    OK' if 'content' in r else '    ERROR: '+str(r.get('message','unknown')))"
    sleep 0.5
  fi
done

echo ""
echo "=== Step 6: Verifying ==="

echo ""
echo "Checking public/ directory..."
curl -s "$API/contents/public?ref=$BRANCH" -H "$AUTH" | python3 -c "
import sys, json
items = json.load(sys.stdin)
if isinstance(items, list):
    for item in items:
        print(f'  {item[\"name\"]} ({item.get(\"type\",\"?\")})')
else:
    print(f'  ERROR: {items.get(\"message\",\"unknown\")}')
"

echo ""
echo "Checking public/footer/ directory..."
curl -s "$API/contents/public/footer?ref=$BRANCH" -H "$AUTH" | python3 -c "
import sys, json
items = json.load(sys.stdin)
if isinstance(items, list):
    for item in items:
        print(f'  {item[\"name\"]} ({item.get(\"type\",\"?\")})')
else:
    print(f'  ERROR: {items.get(\"message\",\"unknown\")}')
"

echo ""
echo "Checking root level..."
curl -s "$API/contents?ref=$BRANCH" -H "$AUTH" | python3 -c "
import sys, json
items = json.load(sys.stdin)
if isinstance(items, list):
    for item in items:
        name = item['name']
        if name.endswith(('.jpg', '.png', '.svg', '.ico')):
            print(f'  ROOT IMAGE (should be deleted): {name}')
    else:
        print('  No stray images at root.')
"

echo ""
echo "=== DONE ==="
echo "Now go to Render dashboard and:"
echo "1. Set Start Command: uvicorn anime_scraper:app --host 0.0.0.0 --port \$PORT"
echo "2. Click Manual Deploy -> Clear build cache & deploy"
