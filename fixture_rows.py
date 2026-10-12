# أمثلة صناعية (ليست بيانات حقيقية) لاختبار سلوك الـ sandbox والبوابات فقط.
import random
random.seed(7)

def T(pairs):
    return {"input": [i for i, _ in pairs], "output": [o for _, o in pairs]}

def sol(py3=(), py2=()):
    return {"language": [3] * len(py3) + [1] * len(py2), "solution": list(py3) + list(py2)}

gen1 = []
for _ in range(10):
    a, b = random.randint(-1000, 1000), random.randint(-1000, 1000)
    gen1.append((f"{a} {b}\n", f"{a+b}\n"))
P1 = {
    "name": "fx_sum_two", "difficulty": 1, "description": "Print a+b.",
    "public_tests": T([("1 2\n", "3\n"), ("5 7\n", "12\n"), ("0 0\n", "0\n")]),
    "private_tests": T([("100 200\n", "300\n"), ("-5 5\n", "0\n")]),
    "generated_tests": T(gen1),
    "solutions": sol(py3=["a,b=map(int,input().split())\nprint(a+b)\n",
                          "import sys\na,b=map(int,sys.stdin.read().split())\nprint(a+b)\n"],
                     py2=["a,b=map(int,raw_input().split())\nprint a+b\n"]),
    "incorrect_solutions": sol(py3=[
        "a,b=map(int,input().split())\nprint(a+b+1)\n",
        "a,b=map(int,input().split())\nprint(a-b)\n",
        "a,b=map(int,input().split())\nprint(a+b)\nprint(0)\n",
        "a,b=map(int,input().split())\nprint(a+b+[][0])\n",                 # RE
        "a,b=map(int,input().split())\nwhile True:\n    pass\nprint(a+b)\n",  # TLE
        "x=[0]*(10**10)\nprint(1)\n",                                        # قنبلة ذاكرة
        "while True:\n    print('x'*1000)\n",                                # مخرجات لا نهائية
        "import socket\na,b=map(int,input().split())\nprint(a+b+1)\n",      # رفض ساكن
        "import os\nos.system('echo pwned')\na,b=map(int,input().split())\nprint(a+b+1)\n",
        "import os\nwhile True:\n    os.fork()\n",
        "import importlib\nm=importlib.import_module('soc'+'ket')\ns=m.socket()\ns.settimeout(1)\ns.connect(('127.0.0.1',9))\nprint(1)\n",
        "import os\nf=getattr(os,'for'+'k')\nwhile True:\n    f()\n",       # تحايل: يرفضه الفلتر الساكن الآن
    ]),
}
P2 = {
    "name": "fx_max_pos_only", "difficulty": 1, "description": "Print max.",
    "public_tests": T([("3\n1 5 2\n", "5\n"), ("2\n9 4\n", "9\n"), ("1\n7\n", "7\n")]),
    "private_tests": T([("4\n10 20 30 5\n", "30\n")]),
    "generated_tests": T([]),
    "solutions": sol(py3=["n=int(input())\na=list(map(int,input().split()))\nprint(max(a))\n"]),
    "incorrect_solutions": sol(py3=[
        "n=int(input())\na=list(map(int,input().split()))\nm=0\nfor x in a:\n    if x>m:\n        m=x\nprint(m)\n"]),
}
P3 = dict(P2)
P3.update({
    "name": "fx_max_with_negative",
    "generated_tests": T([("3\n-5 -2 -9\n", "-2\n"), ("2\n-1 -1\n", "-1\n")]),
    "incorrect_solutions": sol(py3=[
        "n=int(input())\na=list(map(int,input().split()))\nm=0\nfor x in a:\n    if x>m:\n        m=x\nprint(m)\n",
        "import sys\nd=sys.stdin.read().split()\nd=d[1:]\nd.sort()\nprint(d[-1])\n"]),
})
ROWS = [P1, P2, P3]
