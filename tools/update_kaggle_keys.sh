#!/data/data/com.termux/files/usr/bin/bash
# يحدّث مفاتيح Kaggle واحداً واحداً بأمان

echo "═══ تحديث مفاتيح Kaggle ═══"
echo ""

# الحساب الأول
echo "── الحساب 1 ──"
read -p "KAGGLE_USERNAME_1: " U1
read -s -p "KAGGLE_KEY_1: " K1
echo ""
echo "→ رفع الحساب 1..."
railway variables --set "KAGGLE_USERNAME_1=$U1" --service marsad-dashboard --skip-deploys
railway variables --set "KAGGLE_KEY_1=$K1" --service marsad-dashboard --skip-deploys
echo "✓ الحساب 1 محدّث"

echo ""

# الحساب الثاني
echo "── الحساب 2 ──"
read -p "KAGGLE_USERNAME_2: " U2
read -s -p "KAGGLE_KEY_2: " K2
echo ""
echo "→ رفع الحساب 2..."
railway variables --set "KAGGLE_USERNAME_2=$U2" --service marsad-dashboard --skip-deploys
railway variables --set "KAGGLE_KEY_2=$K2" --service marsad-dashboard --skip-deploys
echo "✓ الحساب 2 محدّث"

echo ""
echo "═══ ملخص ═══"
echo "الحساب 1: $U1"
echo "الحساب 2: $U2"
echo ""
echo "الخطوة الأخيرة: railway up --service marsad-dashboard"
