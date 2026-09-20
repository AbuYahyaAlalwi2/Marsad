"""
CYBERGUARD OS — النظام الذكي للوكالات السحابية
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.environ.get("CG_DB_PATH", os.path.join(DATA_DIR, "cyberguard.db"))

# --- النظام ---
CORE_MODEL_PATH = os.environ.get("CG_CORE_MODEL", "models/cyberguard-core")
CORE_QUANTIZED = os.environ.get("CG_QUANTIZED", "true").lower() == "true"

# --- الذاكرة ---
MEMORY_MAX_GB = float(os.environ.get("CG_MEMORY_MAX_GB", "10"))
MEMORY_AUTO_TRAIN = os.environ.get("CG_MEMORY_AUTO_TRAIN", "true").lower() == "true"
MEMORY_AUTO_UPLOAD = os.environ.get("CG_MEMORY_AUTO_UPLOAD", "true").lower() == "true"

# --- الوكلاء ---
MAX_AGENTS = int(os.environ.get("CG_MAX_AGENTS", "1000000"))
AGENT_HIERARCHY_LEVELS = int(os.environ.get("CG_HIERARCHY_LEVELS", "4"))
AGENTS_PER_SUPERVISOR = int(os.environ.get("CG_AGENTS_PER_SUPERVISOR", "100"))
WORKERS_PER_SUPERVISOR = int(os.environ.get("CG_WORKERS_PER_SUPERVISOR", "10"))
AGENTS_PER_WORKER = int(os.environ.get("CG_AGENTS_PER_WORKER", "1000"))

# --- الدمج ---
MERGE_MODELS = [
    {"name": "qwen-coder-32b", "path": "Qwen/Qwen2.5-Coder-32B-Instruct", "weight": 0.30, "role": "code", "free": True},
    {"name": "deepseek-coder", "path": "deepseek-ai/DeepSeek-Coder-V2-Instruct", "weight": 0.25, "role": "logic", "free": True},
    {"name": "codellama-34b", "path": "codellama/CodeLlama-34b-Instruct", "weight": 0.15, "role": "code", "free": True},
    {"name": "wizardcoder-33b", "path": "WizardLMTeam/WizardCoder-33B-V1.1", "weight": 0.15, "role": "solve", "free": True},
    {"name": "phind-codellama", "path": "Phind/Phind-CodeLlama-34B-v2", "weight": 0.10, "role": "tech", "free": True},
    {"name": "kimi-k3", "path": "MoonshotAI/Kimi-K3", "weight": 0.05, "role": "reasoning", "free": True},
    {"name": "llama-3.1-70b", "path": "meta-llama/Meta-Llama-3.1-70B-Instruct", "weight": 0.20, "role": "general", "free": True},
    {"name": "mixtral-8x7b", "path": "mistralai/Mixtral-8x7B-Instruct-v0.1", "weight": 0.15, "role": "general", "free": True},
]

# --- مزودي API (25+ مزود مجاني) ---
API_PROVIDERS = {
    # LLM Providers (15+)
    "google_gemini": {
        "name": "Google Gemini",
        "api_url": "https://generativelanguage.googleapis.com/v1beta",
        "auth_type": "api_key",
        "env_key": "GOOGLE_API_KEY",
        "free_tier": True,
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "category": "llm",
        "rate_limit": 60
    },
    "groq": {
        "name": "Groq",
        "api_url": "https://api.groq.com/openai/v1",
        "auth_type": "bearer",
        "env_key": "GROQ_API_KEY",
        "free_tier": True,
        "models": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768", "llama-3.1-8b-instant"],
        "category": "llm",
        "rate_limit": 30
    },
    "cerebras": {
        "name": "Cerebras",
        "api_url": "https://api.cerebras.ai/v1",
        "auth_type": "bearer",
        "env_key": "CEREBRAS_API_KEY",
        "free_tier": True,
        "models": ["llama-3.1-70b", "llama-3.1-8b"],
        "category": "llm",
        "rate_limit": 30
    },
    "mistral": {
        "name": "Mistral AI",
        "api_url": "https://api.mistral.ai/v1",
        "auth_type": "bearer",
        "env_key": "MISTRAL_API_KEY",
        "free_tier": True,
        "models": ["mistral-large-latest", "codestral-latest", "mistral-small-latest"],
        "category": "llm",
        "rate_limit": 30
    },
    "openrouter": {
        "name": "OpenRouter",
        "api_url": "https://openrouter.ai/api/v1",
        "auth_type": "bearer",
        "env_key": "OPENROUTER_API_KEY",
        "free_tier": True,
        "models": ["qwen/qwen-2.5-coder-32b-instruct", "deepseek/deepseek-coder-v2", "openai/gpt-4o-mini"],
        "category": "llm",
        "rate_limit": 100
    },
    "huggingface": {
        "name": "Hugging Face",
        "api_url": "https://api-inference.huggingface.co",
        "auth_type": "bearer",
        "env_key": "HF_TOKEN",
        "free_tier": True,
        "models": ["Qwen/Qwen2.5-Coder-32B-Instruct", "deepseek-ai/DeepSeek-Coder-V2", "meta-llama/Llama-3.1-70B-Instruct"],
        "category": "llm",
        "rate_limit": 30
    },
    "cohere": {
        "name": "Cohere",
        "api_url": "https://api.cohere.ai/v1",
        "auth_type": "bearer",
        "env_key": "COHERE_API_KEY",
        "free_tier": True,
        "models": ["command-r-plus", "command-r", "command"],
        "category": "llm",
        "rate_limit": 50
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_url": "https://api.deepseek.com/v1",
        "auth_type": "bearer",
        "env_key": "DEEPSEEK_API_KEY",
        "free_tier": True,
        "models": ["deepseek-chat", "deepseek-coder"],
        "category": "llm",
        "rate_limit": 100
    },
    "together": {
        "name": "Together AI",
        "api_url": "https://api.together.xyz/v1",
        "auth_type": "bearer",
        "env_key": "TOGETHER_API_KEY",
        "free_tier": True,
        "models": ["Qwen/Qwen2.5-Coder-32B-Instruct", "deepseek-ai/DeepSeek-Coder-V2-Instruct", "meta-llama/Llama-3.1-70B-Instruct"],
        "category": "llm",
        "rate_limit": 100
    },
    "fireworks": {
        "name": "Fireworks AI",
        "api_url": "https://api.fireworks.ai/inference/v1",
        "auth_type": "bearer",
        "env_key": "FIREWORKS_API_KEY",
        "free_tier": True,
        "models": ["accounts/fireworks/models/qwen2p5-coder-32b-instruct", "accounts/fireworks/models/llama-3.1-70b-instruct"],
        "category": "llm",
        "rate_limit": 50
    },
    "replicate": {
        "name": "Replicate",
        "api_url": "https://api.replicate.com/v1",
        "auth_type": "token",
        "env_key": "REPLICATE_API_TOKEN",
        "free_tier": True,
        "models": ["qwen/qwen-2.5-coder-32b", "meta/llama-3.1-70b-instruct"],
        "category": "llm",
        "rate_limit": 50
    },
    "cloudflare_workers_ai": {
        "name": "Cloudflare Workers AI",
        "api_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
        "auth_type": "bearer",
        "env_key": "CLOUDFLARE_API_TOKEN",
        "free_tier": True,
        "models": ["@cf/qwen/qwen1.5-14b", "@cf/meta/llama-3.1-8b-instruct"],
        "category": "llm",
        "rate_limit": 100
    },
    "nvidia_nim": {
        "name": "NVIDIA NIM",
        "api_url": "https://integrate.api.nvidia.com/v1",
        "auth_type": "bearer",
        "env_key": "NVIDIA_API_KEY",
        "free_tier": True,
        "models": ["meta/llama-3.1-70b-instruct", "mistralai/mixtral-8x7b-instruct"],
        "category": "llm",
        "rate_limit": 50
    },
    "sambanova": {
        "name": "SambaNova",
        "api_url": "https://api.sambanova.ai/v1",
        "auth_type": "bearer",
        "env_key": "SAMBANOVA_API_KEY",
        "free_tier": True,
        "models": ["llama-3.1-70b-instruct", "llama-3.1-8b-instruct"],
        "category": "llm",
        "rate_limit": 30
    },
    "ai21": {
        "name": "AI21 Labs",
        "api_url": "https://api.ai21.com/studio/v1",
        "auth_type": "bearer",
        "env_key": "AI21_API_KEY",
        "free_tier": True,
        "models": ["jamba-1.5-large", "jamba-1.5-mini"],
        "category": "llm",
        "rate_limit": 50
    },
    "baseten": {
        "name": "Baseten",
        "api_url": "https://api.baseten.co/v1",
        "auth_type": "bearer",
        "env_key": "BASETEN_API_KEY",
        "free_tier": True,
        "models": ["qwen-2.5-coder-32b", "meta-llama-3.1-70b-instruct"],
        "category": "llm",
        "rate_limit": 50
    },
    "perplexity": {
        "name": "Perplexity AI",
        "api_url": "https://api.perplexity.ai",
        "auth_type": "bearer",
        "env_key": "PERPLEXITY_API_KEY",
        "free_tier": True,
        "models": ["sonar-pro", "sonar-small", "llama-3.1-70b-instruct"],
        "category": "llm",
        "rate_limit": 50
    },
    
    # Embedding Providers (5+)
    "cohere_embed": {
        "name": "Cohere Embed",
        "api_url": "https://api.cohere.ai/v1/embed",
        "auth_type": "bearer",
        "env_key": "COHERE_API_KEY",
        "free_tier": True,
        "models": ["embed-english-v3.0", "embed-multilingual-v3.0"],
        "category": "embedding",
        "rate_limit": 100
    },
    "jina": {
        "name": "Jina AI",
        "api_url": "https://api.jina.ai/v1",
        "auth_type": "bearer",
        "env_key": "JINA_API_KEY",
        "free_tier": True,
        "models": ["jina-embeddings-v3", "jina-embeddings-v2"],
        "category": "embedding",
        "rate_limit": 100
    },
    "voyage": {
        "name": "Voyage AI",
        "api_url": "https://api.voyageai.com/v1",
        "auth_type": "bearer",
        "env_key": "VOYAGE_API_KEY",
        "free_tier": True,
        "models": ["voyage-3", "voyage-code-3", "voyage-2"],
        "category": "embedding",
        "rate_limit": 100
    },
    "text_embedding_ada_002": {
        "name": "OpenAI Embeddings",
        "api_url": "https://api.openai.com/v1",
        "auth_type": "bearer",
        "env_key": "OPENAI_API_KEY",
        "free_tier": False,
        "models": ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"],
        "category": "embedding",
        "rate_limit": 100
    },
    "sentence_transformers": {
        "name": "Sentence Transformers",
        "api_url": "https://api-inference.huggingface.co",
        "auth_type": "bearer",
        "env_key": "HF_TOKEN",
        "free_tier": True,
        "models": ["sentence-transformers/all-mpnet-base-v2", "sentence-transformers/all-MiniLM-L6-v2"],
        "category": "embedding",
        "rate_limit": 50
    },
    
    # Code-Specific Providers (5+)
    "codestral": {
        "name": "Codestral (Mistral)",
        "api_url": "https://api.mistral.ai/v1",
        "auth_type": "bearer",
        "env_key": "MISTRAL_API_KEY",
        "free_tier": True,
        "models": ["codestral-latest"],
        "category": "code",
        "rate_limit": 30
    },
    "deepseek_code": {
        "name": "DeepSeek Coder",
        "api_url": "https://api.deepseek.com/v1",
        "auth_type": "bearer",
        "env_key": "DEEPSEEK_API_KEY",
        "free_tier": True,
        "models": ["deepseek-coder", "deepseek-chat"],
        "category": "code",
        "rate_limit": 100
    },
    "sourcegraph_cody": {
        "name": "Sourcegraph Cody",
        "api_url": "https://api.sourcegraph.com/v1",
        "auth_type": "token",
        "env_key": "SOURCEGRAPH_TOKEN",
        "free_tier": True,
        "models": ["cody-code", "cody-chat"],
        "category": "code",
        "rate_limit": 50
    },
    "github_copilot": {
        "name": "GitHub Copilot",
        "api_url": "https://api.github.com/copilot/v1",
        "auth_type": "token",
        "env_key": "GITHUB_TOKEN",
        "free_tier": True,
        "models": ["copilot-code", "copilot-chat"],
        "category": "code",
        "rate_limit": 50
    },
    "tabnine": {
        "name": "Tabnine",
        "api_url": "https://api.tabnine.com/v1",
        "auth_type": "bearer",
        "env_key": "TABNINE_API_KEY",
        "free_tier": True,
        "models": ["tabnine-code", "tabnine-chat"],
        "category": "code",
        "rate_limit": 50
    },
}

# --- منصات جمع البيانات (20+ منصة حقيقية) ---
DATASET_PLATFORMS = {
    # منصات الكود
    "github": {
        "name": "GitHub",
        "type": "code",
        "api": "https://api.github.com",
        "auth": {"token": "GITHUB_TOKEN"},
        "free": True,
        "rate_limit": 5000,
        "region_specific": False
    },
    "gitlab": {
        "name": "GitLab",
        "type": "code",
        "api": "https://gitlab.com/api/v4",
        "auth": {"token": "GITLAB_TOKEN"},
        "free": True,
        "rate_limit": 1000,
        "region_specific": False
    },
    "bitbucket": {
        "name": "Bitbucket",
        "type": "code",
        "api": "https://api.bitbucket.org/2.0",
        "auth": {"username": "BITBUCKET_USERNAME", "app_password": "BITBUCKET_APP_PASSWORD"},
        "free": True,
        "rate_limit": 1000,
        "region_specific": False
    },
    "sourcegraph": {
        "name": "Sourcegraph",
        "type": "code",
        "api": "https://api.sourcegraph.com/v1",
        "auth": {"token": "SOURCEGRAPH_TOKEN"},
        "free": True,
        "rate_limit": 1000,
        "region_specific": False
    },
    
    # منصات الأمن
    "exploitdb": {
        "name": "ExploitDB",
        "type": "security",
        "api": "https://raw.githubusercontent.com/offensive-security/exploitdb/main",
        "auth": None,
        "free": True,
        "rate_limit": 1000,
        "region_specific": False
    },
    "cve": {
        "name": "CVE/NVD",
        "type": "security",
        "api": "https://services.nvd.nist.gov/rest/json/cves/2.0",
        "auth": {"key": "NVD_API_KEY"},
        "free": True,
        "rate_limit": 5,
        "region_specific": False
    },
    "packetstorm": {
        "name": "PacketStorm",
        "type": "security",
        "api": "https://packetstormsecurity.com",
        "scrape": True,
        "auth": None,
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "metasploit": {
        "name": "Metasploit DB",
        "type": "security",
        "api": "https://raw.githubusercontent.com/rapid7/metasploit-framework/master",
        "auth": None,
        "free": True,
        "rate_limit": 1000,
        "region_specific": False
    },
    "vulners": {
        "name": "Vulners",
        "type": "security",
        "api": "https://vulners.com/api/v3",
        "auth": {"key": "VULNERS_API_KEY"},
        "free": True,
        "rate_limit": 50,
        "region_specific": False
    },
    "shodan": {
        "name": "Shodan",
        "type": "security",
        "api": "https://api.shodan.io",
        "auth": {"key": "SHODAN_API_KEY"},
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "virus_total": {
        "name": "VirusTotal",
        "type": "security",
        "api": "https://www.virustotal.com/api/v3",
        "auth": {"key": "VIRUSTOTAL_API_KEY"},
        "free": True,
        "rate_limit": 4,
        "region_specific": False
    },
    "alienvault_otx": {
        "name": "AlienVault OTX",
        "type": "security",
        "api": "https://otx.alienvault.com/api/v1",
        "auth": {"key": "OTX_API_KEY"},
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "threatfox": {
        "name": "ThreatFox",
        "type": "security",
        "api": "https://threatfox-api.abuse.ch/api/v1",
        "auth": None,
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    
    # منصات البيانات
    "huggingface_datasets": {
        "name": "HuggingFace Datasets",
        "type": "dataset",
        "api": "https://huggingface.co/api/datasets",
        "auth": {"token": "HF_TOKEN"},
        "free": True,
        "rate_limit": 1000,
        "region_specific": False
    },
    "kaggle": {
        "name": "Kaggle",
        "type": "dataset",
        "api": "https://www.kaggle.com/api/v1",
        "auth": {"username": "KAGGLE_USERNAME", "key": "KAGGLE_KEY"},
        "free": True,
        "rate_limit": 20,
        "region_specific": False
    },
    "google_dataset_search": {
        "name": "Google Dataset Search",
        "type": "dataset",
        "api": "https://datasetsearch.research.google.com/api",
        "auth": {"key": "GOOGLE_API_KEY"},
        "free": True,
        "rate_limit": 100,
        "region_specific": True,
        "regions": ["global"]
    },
    
    "uci": {
        "name": "UCI Machine Learning Repository",
        "type": "dataset",
        "api": "https://archive.ics.uci.edu/api/datasets",
        "auth": None,
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "openml": {
        "name": "OpenML",
        "type": "dataset",
        "api": "https://www.openml.org/api/v1/json",
        "auth": {"key": "OPENML_API_KEY"},
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "google_research_datasets": {
        "name": "Google Research Datasets",
        "type": "dataset",
        "api": "https://www.tensorflow.org/datasets",
        "auth": None,
        "free": True,
        "rate_limit": 50,
        "region_specific": False
    },
    "opus": {
        "name": "OPUS Parallel Corpora",
        "type": "dataset",
        "api": "https://opus.nlpl.eu",
        "auth": None,
        "free": True,
        "rate_limit": 50,
        "region_specific": False
    },
"common_crawl": {
        "name": "Common Crawl",
        "type": "web",
        "api": "https://index.commoncrawl.org",
        "auth": None,
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "ccindex": {
        "name": "CCIndex",
        "type": "web",
        "api": "https://api.commoncrawl.org",
        "auth": None,
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    
    # مجموعات البيانات الكبيرة
    "redpajama": {
        "name": "RedPajama",
        "type": "dataset",
        "api": "https://huggingface.co/datasets/togethercomputer/RedPajama-Data-1T",
        "auth": {"token": "HF_TOKEN"},
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "the_pile": {
        "name": "The Pile",
        "type": "dataset",
        "api": "https://huggingface.co/datasets/EleutherAI/the_pile",
        "auth": {"token": "HF_TOKEN"},
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "dolma": {
        "name": "Dolma",
        "type": "dataset",
        "api": "https://huggingface.co/datasets/allenai/dolma",
        "auth": {"token": "HF_TOKEN"},
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "starcoder": {
        "name": "StarCoder",
        "type": "dataset",
        "api": "https://huggingface.co/datasets/bigcode/starcoderdata",
        "auth": {"token": "HF_TOKEN"},
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    
    # منصات الأسئلة والأجوبة
    "stackoverflow": {
        "name": "StackOverflow",
        "type": "qa",
        "api": "https://api.stackexchange.com/2.3",
        "auth": None,
        "free": True,
        "rate_limit": 300,
        "region_specific": False
    },
    "stackexchange": {
        "name": "StackExchange",
        "type": "qa",
        "api": "https://api.stackexchange.com/2.3",
        "auth": None,
        "free": True,
        "rate_limit": 300,
        "region_specific": False
    },
    
    # منصات التعلم الآلي
    "paperswithcode": {
        "name": "Papers with Code",
        "type": "research",
        "api": "https://paperswithcode.com/api/v1",
        "auth": None,
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    "arxiv": {
        "name": "arXiv",
        "type": "research",
        "api": "https://export.arxiv.org/api/query",
        "auth": None,
        "free": True,
        "rate_limit": 100,
        "region_specific": False
    },
    
    # منصات السحابة (للتوزيع الجغرافي)
    "gcp_regions": {
        "name": "Google Cloud Regions",
        "type": "cloud",
        "api": "https://cloud.googleapis.com",
        "auth": {"key": "GCP_API_KEY"},
        "free": True,
        "rate_limit": 100,
        "region_specific": True,
        "regions": ["us-central1", "us-east1", "europe-west1", "asia-east1"]
    },
    "aws_regions": {
        "name": "AWS Regions",
        "type": "cloud",
        "api": "https://ec2.amazonaws.com",
        "auth": {"key": "AWS_ACCESS_KEY_ID", "secret": "AWS_SECRET_ACCESS_KEY", "region": "AWS_DEFAULT_REGION"},
        "free": True,
        "rate_limit": 100,
        "region_specific": True,
        "regions": ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
    },
    "azure_regions": {
        "name": "Azure Regions",
        "type": "cloud",
        "api": "https://management.azure.com",
        "auth": {"key": "AZURE_API_KEY"},
        "free": True,
        "rate_limit": 100,
        "region_specific": True,
        "regions": ["eastus", "westeurope", "southeastasia"]
    },
}

# --- مزودي السحابة ---
CLOUD_PROVIDERS = [
    {"name": "gcp", "max_agents": 100000, "region": "us-central1", "free_tier": True, "region_specific": True},
    {"name": "oracle", "max_agents": 200000, "region": "us-ashburn-1", "free_tier": True, "region_specific": True},
    {"name": "aws", "max_agents": 150000, "region": "us-east-1", "free_tier": True, "region_specific": True},
    {"name": "azure", "max_agents": 100000, "region": "eastus", "free_tier": True, "region_specific": True},
    {"name": "cloudflare", "max_agents": 50000, "region": "auto", "free_tier": True, "region_specific": False},
    {"name": "fly", "max_agents": 30000, "region": "auto", "free_tier": True, "region_specific": False},
    {"name": "railway", "max_agents": 20000, "region": "auto", "free_tier": True, "region_specific": False},
    {"name": "render", "max_agents": 20000, "region": "auto", "free_tier": True, "region_specific": False},
    {"name": "kaggle", "max_agents": 50000, "region": "auto", "free_tier": True, "region_specific": False},
    {"name": "colab", "max_agents": 50000, "region": "auto", "free_tier": True, "region_specific": False},
    {"name": "replit", "max_agents": 10000, "region": "auto", "free_tier": True, "region_specific": False},
    {"name": "huggingface_spaces", "max_agents": 10000, "region": "auto", "free_tier": True, "region_specific": False},
]

# --- مزودي Proxy ---
PROXY_PROVIDERS = {
    "luminati": {"name": "Luminati", "api": "https://api.luminati.io", "auth": "LUMINATI_API_KEY", "free_tier": False},
    "smartproxy": {"name": "SmartProxy", "api": "https://api.smartproxy.com", "auth": "SMARTPROXY_API_KEY", "free_tier": False},
    "oxylabs": {"name": "OxyLabs", "api": "https://api.oxylabs.io", "auth": "OXYLABS_API_KEY", "free_tier": False},
    "brightdata": {"name": "BrightData", "api": "https://api.brightdata.com", "auth": "BRIGHTDATA_API_KEY", "free_tier": False},
    "scraperapi": {"name": "ScraperAPI", "api": "https://api.scraperapi.com", "auth": "SCRAPERAPI_API_KEY", "free_tier": True},
}

# --- منصات المصادر (8+ منصات ذات جودة عالية) ---
SOURCE_PLATFORMS = {
    "github": {"weight": 0.4, "priority": 1, "quality": "high"},
    "gitlab": {"weight": 0.3, "priority": 2, "quality": "high"},
    "huggingface": {"weight": 0.5, "priority": 1, "quality": "high"},
    "exploitdb": {"weight": 0.4, "priority": 1, "quality": "high"},
    "cve": {"weight": 0.5, "priority": 1, "quality": "high"},
    "packetstorm": {"weight": 0.3, "priority": 2, "quality": "high"},
    "stackoverflow": {"weight": 0.4, "priority": 2, "quality": "high"},
    "kaggle": {"weight": 0.3, "priority": 3, "quality": "medium"},
    "common_crawl": {"weight": 0.2, "priority": 4, "quality": "medium"},
    "arxiv": {"weight": 0.3, "priority": 2, "quality": "high"},
    "paperswithcode": {"weight": 0.3, "priority": 2, "quality": "high"},
    "vulners": {"weight": 0.3, "priority": 2, "quality": "high"},
    "shodan": {"weight": 0.3, "priority": 2, "quality": "high"},
    "virus_total": {"weight": 0.2, "priority": 3, "quality": "medium"},
    "metasploit": {"weight": 0.2, "priority": 3, "quality": "medium"},
    "sourcegraph": {"weight": 0.4, "priority": 1, "quality": "high"},
    "redpajama": {"weight": 0.4, "priority": 1, "quality": "high"},
    "the_pile": {"weight": 0.3, "priority": 2, "quality": "high"},
    "dolma": {"weight": 0.3, "priority": 2, "quality": "high"},
    "starcoder": {"weight": 0.3, "priority": 2, "quality": "high"},
}

# --- إعدادات مانع الخمول ---
KEEP_ALIVE_INTERVAL = int(os.environ.get("CG_KEEP_ALIVE_INTERVAL", "300"))
MAX_RETRIES = int(os.environ.get("CG_MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.environ.get("CG_REQUEST_TIMEOUT", "60"))

# --- إعدادات VPN ---
ENABLE_VPN = os.environ.get("CG_ENABLE_VPN", "false").lower() == "true"
VPN_PROVIDER = os.environ.get("CG_VPN_PROVIDER", "protonvpn")
VPN_COUNTRY = os.environ.get("CG_VPN_COUNTRY", None)
VPN_AUTO_CONNECT = os.environ.get("CG_VPN_AUTO_CONNECT", "false").lower() == "true"
VPN_ROTATE_INTERVAL = int(os.environ.get("CG_VPN_ROTATE_INTERVAL", "3600"))

# --- إعدادات Proxy ---
ENABLE_PROXY = os.environ.get("CG_ENABLE_PROXY", "false").lower() == "true"
PROXY_TYPE = os.environ.get("CG_PROXY_TYPE", "http")
PROXY_HOST = os.environ.get("CG_PROXY_HOST", None)
PROXY_PORT = int(os.environ.get("CG_PROXY_PORT", "8080"))
PROXY_USERNAME = os.environ.get("CG_PROXY_USERNAME", None)
PROXY_PASSWORD = os.environ.get("CG_PROXY_PASSWORD", None)

# --- إعدادات حفظ المفاتيح ---
# طريقة 1: متغيرات بيئة (مفضل)
# طريقة 2: ملف .env
# طريقة 3: قاعدة البيانات (مشفرة)
KEY_STORAGE_METHOD = os.environ.get("CG_KEY_STORAGE", "env")  # env, file, db

# --- إعدادات توليد الاستغلالات (Exploit Generation) ---
ENABLE_EXPLOIT_GENERATION = os.environ.get("CG_ENABLE_EXPLOIT_GEN", "false").lower() == "true"
EXPLOIT_OUTPUT_DIR = os.environ.get("CG_EXPLOIT_OUTPUT_DIR", os.path.join(BASE_DIR, "exploits"))
EXPLOIT_TEST_ENV = os.environ.get("CG_EXPLOIT_TEST_ENV", "sandbox")
EXPLOIT_AUTO_TEST = os.environ.get("CG_EXPLOIT_AUTO_TEST", "false").lower() == "true"
EXPLOIT_MAX_RETRIES = int(os.environ.get("CG_EXPLOIT_MAX_RETRIES", "3"))

# --- إعدادات الدارك ويب (لجمع الثغرات) ---
ENABLE_DARKWEB_MONITORING = os.environ.get("CG_ENABLE_DARKWEB", "true").lower() == "true"
DARKWEB_SCRAPE_INTERVAL = int(os.environ.get("CG_DARKWEB_INTERVAL", "3600"))
DARKWEB_USER_AGENT = os.environ.get("CG_DARKWEB_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0")

# منتديات + مصادر ثغرات (كليرنت + دارك)
DARKWEB_FORUMS = [
    # Clearnet security forums / sources
    {"name": "0x00sec", "url": "https://0x00sec.org", "enabled": True, "tor": False},
    {"name": "HackForums", "url": "https://hackforums.net", "enabled": True, "tor": False},
    {"name": "Exploit.in", "url": "https://exploit.in", "enabled": True, "tor": False},
    {"name": "Reddit_netsec", "url": "https://www.reddit.com/r/netsec/.rss", "enabled": True, "tor": False},
    {"name": "Reddit_ExploitDev", "url": "https://www.reddit.com/r/ExploitDev/.rss", "enabled": True, "tor": False},
    {"name": "PacketStorm", "url": "https://packetstormsecurity.com/", "enabled": True, "tor": False},
    {"name": "ExploitDB", "url": "https://www.exploit-db.com/", "enabled": True, "tor": False},
    {"name": "NVD_Recent", "url": "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=20", "enabled": True, "tor": False},
    {"name": "GitHub_Advisories", "url": "https://api.github.com/advisories?per_page=20", "enabled": True, "tor": False},
    {"name": "CVE_Mitre", "url": "https://cve.mitre.org/data/downloads/allitems.csv", "enabled": False, "tor": False},
    {"name": "Sploitus", "url": "https://sploitus.com/", "enabled": True, "tor": False},
    {"name": "Vulners", "url": "https://vulners.com/", "enabled": True, "tor": False},
    {"name": "CXSecurity", "url": "https://cxsecurity.com/wlb/", "enabled": True, "tor": False},
    {"name": "OpenBugBounty", "url": "https://www.openbugbounty.org/", "enabled": True, "tor": False},
    # Tor / dark oriented (need Tor proxy)
    {"name": "Dread", "url": "http://dreadytofatroptsdj6io7l3xptbet6onoyno2ycvqf7loenubwp2liid.onion", "enabled": True, "tor": True},
    {"name": "Tor_Links_Hub", "url": "http://zqktlwiuavvvqqt4ybvgvi7tyo4hjl5xgfuvpdf6otcjiycgwqbym.onion", "enabled": False, "tor": True},
]

# مصادر كليرنت API للثغرات (حماية ذاتية)
CLEARNET_VULN_SOURCES = {
    "nvd": {
        "name": "NVD NIST",
        "api": "https://services.nvd.nist.gov/rest/json/cves/2.0",
        "type": "json",
        "enabled": True,
    },
    "github_advisories": {
        "name": "GitHub Security Advisories",
        "api": "https://api.github.com/advisories",
        "type": "json",
        "enabled": True,
    },
    "exploitdb_github": {
        "name": "Exploit-DB (GitHub mirror)",
        "api": "https://raw.githubusercontent.com/offensive-security/exploitdb/main/files_exploits.csv",
        "type": "csv",
        "enabled": True,
    },
    "cisa_kev": {
        "name": "CISA Known Exploited Vulnerabilities",
        "api": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        "type": "json",
        "enabled": True,
    },
    "osv": {
        "name": "OSV.dev",
        "api": "https://api.osv.dev/v1/query",
        "type": "json",
        "enabled": True,
    },
}

# --- إعدادات منع التكرار ---
# استخدام hash للبيانات
DUPLICATE_CHECK_ENABLED = os.environ.get("CG_DUPLICATE_CHECK", "true").lower() == "true"
DUPLICATE_CHECK_FIELD = "content_hash"  # لحقل memory

# --- إعدادات جمع الوكلاء ---
# منع جمع البيانات المكررة
AGENT_COLLECTION_DUPLICATE_CHECK = True
AGENT_COLLECTION_INTERVAL = int(os.environ.get("CG_COLLECTION_INTERVAL", "3600"))  # ساعة

# --- إنشاء الدلائل ---
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "models"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "plugins"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "datasets"), exist_ok=True)
os.makedirs(EXPLOIT_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "darkweb_cache"), exist_ok=True)
