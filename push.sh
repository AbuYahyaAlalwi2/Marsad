#!/bin/bash
git config --global --add safe.directory "$(pwd)" 2>/dev/null
git config user.name "AbuYahyaAlalwi2"
git config user.email "AbuYahyaAlalwi2@users.noreply.github.com"

echo "Enter GitHub Token:"
read -s TOKEN

git add .
git commit -m "ONE-CLICK automation - REAL data"
git remote remove origin 2>/dev/null
git remote add origin "https://${TOKEN}@github.com/AbuYahyaAlalwi2/Marsad.git"
git branch -M main
git push -u origin main --force

echo "✓ Pushed successfully!"
echo "Now go to Render → Manual Deploy → Deploy latest commit"
