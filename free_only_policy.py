"""Free/authorized runtime configuration.

Paid infrastructure and automated account creation are disabled by default.
Credentials must belong to the operator and be supplied through environment
variables or official OAuth integrations.
"""
import os

# Keep existing settings, but make potentially costly/unsafe automation opt-in.
# These assignments are intentionally last so they override legacy defaults.
ENABLE_DARKWEB_MONITORING = False
ENABLE_EXPLOIT_GENERATION = False
ENABLE_VPN = os.environ.get("CG_ENABLE_VPN", "false").lower() == "true"
MEMORY_AUTO_UPLOAD = os.environ.get("MEMORY_AUTO_UPLOAD", "false").lower() == "true"
FREE_ONLY = True
ALLOW_AUTOMATED_SIGNUP = False
REQUIRE_OPERATOR_CREDENTIALS = True

# Never treat a provider as free merely because an old registry says free.
PAID_OR_BILLING_PROVIDERS = {
    "aws", "gcp", "azure", "oracle", "render", "railway", "fly",
    "replicate", "together", "fireworks", "perplexity", "baseten",
}
