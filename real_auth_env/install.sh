#!/bin/bash
# Smart Installer - Detects Environment and Installs Accordingly

echo "🔍 جاري فحص البيئة..."

if [ -d "/kaggle" ] || [ ! -z "$E2B_API_KEY" ]; then
    echo "✅ بيئة سحابية مكتشفة (Kaggle/E2B)."
    
    # تثبيت المكتبات الثقيلة
    pip install torch transformers accelerate bitsandbytes qwen-vl-utils Pillow requests numpy beautifulsoup4
    
    # تثبيت Playwright والمتصفح
    pip install playwright
    playwright install chromium --with-deps
    
    # تثبيت الشاشة الافتراضية (ضرورية لـ headless=False في السحابة)
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y xvfb
    fi
    
else
    echo "⚠️ بيئة Termux محلية مكتشفة."
    echo "   ➡️ يتم تثبيت المكتبات الخفيفة فقط للتحضير."
    
    # تثبيت ما يمكن تثبيته محلياً
    pip install requests beautifulsoup4 Pillow
    
    echo "   ⛔ تنبيه: لا يمكن تشغيل النموذج البصري أو Playwright هنا."
    echo "   ➡️ يرجى نقل هذا المجلد إلى Kaggle/E2B لتشغيل cloud_vision_agent.py"
fi

echo "✅ اكتملت عملية التهيئة."
