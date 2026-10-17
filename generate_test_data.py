import gzip
import random
import os

# تصحيح المسار وضمان وجود المجلد
filepath = os.path.expanduser('~/Marsad/raw_dumps/test_real.csv.gz')
os.makedirs(os.path.dirname(filepath), exist_ok=True)

codes = [
    'def calculate_sum(a, b):\n    return a + b\n\n# This is a simple function',
    'class DataProcessor:\n    def __init__(self):\n        self.data = []\n    def process(self):\n        pass',
    'import os\nimport sys\n\ndef main():\n    print("Hello World")\n    sys.exit(0)',
    'def fetch_data(url):\n    # TODO: implement network request\n    return None',
    'try:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    result = 0'
]

with gzip.open(filepath, 'wt', encoding='utf-8') as f:
    f.write('content,code,text\n')
    for i in range(50000):
        code = random.choice(codes) + f'\n# Variant {i}'
        safe_code = code.replace('"', '""')
        f.write(f'"{safe_code}","{safe_code}","{safe_code}"\n')

print(f'✅ تم إنشاء 50,000 عينة اختبار واقعية بنجاح في: {filepath}')
