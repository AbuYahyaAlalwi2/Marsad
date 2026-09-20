"""
CLoud Providers Database - قاعدة بيانات جميع مزودي السحابة في العالم (200+ مزود)

تصنيف:
- Tier 1: مزودون عالميون (يعملون في جميع دول العالم)
- Tier 2: مزودون إقليميون (يعملون في منطقة واحدة)
- Tier 3: مزودون محليون (يعملون في دولة واحدة فقط)

كل مزود يحتوي على:
- name: اسم المزود
- country: دولة الأصل
- tier: Tier 1, 2, or 3
- regions: قائمة المناطق المتاحة
- free_tier: هل يوجد خطة مجانية
- website: الموقع الرسمي
- api_url: رابط API
- vpn_required: هل يتطلب VPN للدخول من خارج الدولة
- region_specific: هل مقتصر على منطقة محددة
- vpn_country: الدولة التي يجب استخدام VPN لها (إذا لزم الأمر)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CloudProvider:
    """معلومات عن مزود سحابي"""
    name: str
    country: str
    tier: str  # Tier 1, 2, or 3
    regions: List[str] = field(default_factory=list)
    free_tier: bool = False
    website: str = ""
    api_url: str = ""
    vpn_required: bool = False
    region_specific: bool = False
    vpn_country: Optional[str] = None
    auth_required: bool = True
    rate_limit: int = 100
    notes: str = ""


# ============================================================================
# TIER 1: مزودون عالميون (يعملون في جميع دول العالم)
# ============================================================================

TIER_1_PROVIDERS = [
    # الولايات المتحدة
    CloudProvider(
        name="aws",
        country="United States",
        tier="Tier 1",
        regions=[
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3",
            "eu-north-1", "eu-south-1", "ap-east-1", "ap-northeast-1",
            "ap-northeast-2", "ap-northeast-3", "ap-southeast-1", "ap-southeast-2",
            "ap-southeast-3", "ap-southeast-4", "ap-south-1", "ap-south-2",
            "ca-central-1", "me-central-1", "me-south-1", "sa-east-1"
        ],
        free_tier=True,
        website="https://aws.amazon.com",
        api_url="https://ec2.amazonaws.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=100,
        notes="أكبر مزود سحابي في العالم"
    ),
    CloudProvider(
        name="google_cloud",
        country="United States",
        tier="Tier 1",
        regions=[
            "us-central1", "us-east1", "us-east4", "us-west1", "us-west2",
            "us-west3", "us-west4", "europe-central2", "europe-west1",
            "europe-west2", "europe-west3", "europe-west4", "europe-west6",
            "europe-west8", "europe-west9", "europe-north1", "asia-east1",
            "asia-east2", "asia-northeast1", "asia-northeast2", "asia-northeast3",
            "asia-southeast1", "asia-southeast2", "asia-south1", "asia-south2",
            "australia-southeast1", "australia-southeast2", "southamerica-east1",
            "southamerica-west1", "northamerica-northeast1", "northamerica-northeast2"
        ],
        free_tier=True,
        website="https://cloud.google.com",
        api_url="https://cloud.googleapis.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=100,
        notes="منصة Google السحابية"
    ),
    CloudProvider(
        name="azure",
        country="United States",
        tier="Tier 1",
        regions=[
            "eastus", "eastus2", "centralus", "northcentralus", "southcentralus",
            "westus", "westus2", "westus3", "northeurope", "westeurope",
            "francecentral", "germanynorth", "germanywestcentral", "italynorth",
            "norwayeast", "polandcentral", "swedencentral", "switzerlandnorth",
            "switzerlandwest", "ukwest", "uksouth", "eastasia", "southeastasia",
            "australiaeast", "australiacentral", "australiacentral2", "brazilsouth",
            "canadacentral", "canadaeast", "indiawest", "indiacentral", "indiasouth",
            "japanwest", "japaneast", "jioindiawest", "koreacentral", "koreasouth",
            "southafricanorth", "southafricawest", "uaecentral", "uaenorth"
        ],
        free_tier=True,
        website="https://azure.microsoft.com",
        api_url="https://management.azure.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=100,
        notes="منصة Microsoft السحابية"
    ),
    CloudProvider(
        name="oracle_cloud",
        country="United States",
        tier="Tier 1",
        regions=[
            "us-ashburn-1", "us-phoenix-1", "us-sanjose-1", "ca-toronto-1",
            "ca-montreal-1", "uk-london-1", "uk-cardiff-1", "de-frankfurt-1",
            "nl-ams-1", "fr-paris-1", "ch-zurich-1", "it-milan-1",
            "se-stockholm-1", "no-oslo-1", "dk-copenhagen-1", "es-madrid-1",
            "ie-dublin-1", "au-sydney-1", "au-melbourne-1", "in-mumbai-1",
            "in-hyderabad-1", "ap-chuncheon-1", "ap-tokyo-1", "ap-osaka-1",
            "ap-seoul-1", "ap-singapore-1", "ap-sydney-1", "ap-melbourne-1",
            "sa-saopaulo-1", "sa-santiago-1", "me-dubai-1", "me-jerusalem-1",
            "af-johannesburg-1", "za-johannesburg-1"
        ],
        free_tier=True,
        website="https://cloud.oracle.com",
        api_url="https://iaas.api.oraclecloud.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=100,
        notes="Oracle Cloud Infrastructure"
    ),
    CloudProvider(
        name="ibm_cloud",
        country="United States",
        tier="Tier 1",
        regions=[
            "us-south", "us-east", "eu-de", "eu-gb", "eu-es",
            "ap-au", "ap-jp", "ap-jp-tok", "ap-jp-osa"
        ],
        free_tier=False,
        website="https://www.ibm.com/cloud",
        api_url="https://api.us-south.cloud ibm.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=100,
        notes="IBM Cloud"
    ),
    CloudProvider(
        name="digitalocean",
        country="United States",
        tier="Tier 1",
        regions=[
            "nyc1", "nyc2", "nyc3", "sfo1", "sfo2", "sfo3",
            "nyc1", "ams1", "ams2", "ams3", "sgp1", "lon1",
            "fra1", "tor1", "blr1"
        ],
        free_tier=True,
        website="https://www.digitalocean.com",
        api_url="https://api.digitalocean.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=5000,
        notes="DigitalOcean Droplets"
    ),
    CloudProvider(
        name="linode",
        country="United States",
        tier="Tier 1",
        regions=[
            "us-east", "us-west", "us-central", "us-southeast",
            "eu-west", "eu-central", "ap-west", "ap-southeast"
        ],
        free_tier=True,
        website="https://www.linode.com",
        api_url="https://api.linode.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="Linode Cloud"
    ),
    CloudProvider(
        name="vultr",
        country="United States",
        tier="Tier 1",
        regions=[
            "ewr", "dfw", "ord", "lax", "sjc", "sea",
            "lhr", "par", "ams", "fra", "sin", "syd",
            "tyo", "icn", "blr", "sao"
        ],
        free_tier=True,
        website="https://www.vultr.com",
        api_url="https://api.vultr.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="Vultr Cloud"
    ),
    CloudProvider(
        name="hetzner_cloud",
        country="Germany",
        tier="Tier 1",
        regions=["eu-central", "us-east", "us-west", "ap-southeast"],
        free_tier=False,
        website="https://www.hetzner.com/cloud",
        api_url="https://api.hetzner.cloud",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="Hetzner Cloud (ألمانيا)"
    ),
    CloudProvider(
        name="ovhcloud",
        country="France",
        tier="Tier 1",
        regions=[
            "GRA", "RBX", "SBG", "BHS", "DE", "UK",
            "WAW", "US-EAST", "US-WEST", "APAC"
        ],
        free_tier=True,
        website="https://www.ovhcloud.com",
        api_url="https://api.ovh.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="OVHcloud (فرنسا)"
    ),
    CloudProvider(
        name="scaleway",
        country="France",
        tier="Tier 1",
        regions=["fr-par-1", "fr-par-2", "nl-ams-1", "pl-waw-1", "de-fra-1"],
        free_tier=True,
        website="https://www.scaleway.com",
        api_url="https://api.scaleway.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="Scaleway (فرنسا)"
    ),
    CloudProvider(
        name="upcloud",
        country="Finland",
        tier="Tier 1",
        regions=["fi-hel1", "fi-hel2", "de-fra1", "nl-ams1", "sg-sin1", "us-nyc1", "us-sfo1"],
        free_tier=True,
        website="https://upcloud.com",
        api_url="https://api.upcloud.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="UpCloud (فنلندا)"
    ),
    # الصين
    CloudProvider(
        name="alibaba_cloud",
        country="China",
        tier="Tier 1",
        regions=[
            "cn-hangzhou", "cn-shanghai", "cn-qingdao", "cn-beijing",
            "cn-zhangjiakou", "cn-huhehaote", "cn-shenzhen", "cn-chengdu",
            "cn-hongkong", "ap-southeast-1", "ap-southeast-2", "ap-southeast-3",
            "ap-southeast-5", "ap-northeast-1", "eu-central-1", "eu-west-1",
            "us-west-1", "us-east-1", "me-east-1"
        ],
        free_tier=True,
        website="https://www.alibabacloud.com",
        api_url="https://ecs.aliyuncs.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="China",
        auth_required=True,
        rate_limit=1000,
        notes="Alibaba Cloud (الصين) - يتطلب VPN للصين"
    ),
    CloudProvider(
        name="tencent_cloud",
        country="China",
        tier="Tier 1",
        regions=[
            "ap-guangzhou", "ap-shanghai", "ap-beijing", "ap-nanjing",
            "ap-chengdu", "ap-chongqing", "ap-hongkong", "ap-singapore",
            "ap-bangkok", "ap-mumbai", "ap-seoul", "ap-tokyo",
            "na-toronto", "na-siliconvalley", "eu-frankfurt", "eu-moscow"
        ],
        free_tier=True,
        website="https://intl.cloud.tencent.com",
        api_url="https://cvm.tencentcloudapi.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="China",
        auth_required=True,
        rate_limit=1000,
        notes="Tencent Cloud (الصين) - يتطلب VPN للصين"
    ),
    CloudProvider(
        name="huawei_cloud",
        country="China",
        tier="Tier 1",
        regions=[
            "cn-north-1", "cn-north-4", "cn-east-2", "cn-east-3",
            "cn-south-1", "cn-south-4", "cn-southwest-2", "ap-southeast-1",
            "ap-southeast-2", "ap-southeast-3", "la-south-2", "af-south-1",
            "eu-west-101", "sa-brazil-1"
        ],
        free_tier=True,
        website="https://www.huaweicloud.com",
        api_url="https://ecs.otc.t-systems.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="China",
        auth_required=True,
        rate_limit=1000,
        notes="Huawei Cloud (الصين) - يتطلب VPN للصين"
    ),
    CloudProvider(
        name="baidu_cloud",
        country="China",
        tier="Tier 1",
        regions=["bj", "gz", "su", "hz", "sh", "hk", "sg"],
        free_tier=False,
        website="https://cloud.baidu.com",
        api_url="https://bce.baidu.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="China",
        auth_required=True,
        rate_limit=1000,
        notes="Baidu Cloud (الصين) - يتطلب VPN للصين"
    ),
]

# ============================================================================
# TIER 2: مزودون إقليميون (يعملون في منطقة واحدة)
# ============================================================================

TIER_2_PROVIDERS = [
    # أوروبا
    CloudProvider(
        name="ionos",
        country="Germany",
        tier="Tier 2",
        regions=["DE", "ES", "FR", "GB", "IT", "US"],
        free_tier=True,
        website="https://www.ionos.com",
        api_url="https://api.ionos.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="IONOS (ألمانيا) - أوروبا والولايات المتحدة"
    ),
    CloudProvider(
        name="lemonway",
        country="France",
        tier="Tier 2",
        regions=["FR", "DE", "ES", "IT"],
        free_tier=False,
        website="https://www.lemonway.com",
        api_url="https://api.lemonway.com",
        vpn_required=False,
        region_specific=True,
        vpn_country="France",
        auth_required=True,
        rate_limit=500,
        notes="Lemonway (فرنسا) - أوروبا فقط"
    ),
    CloudProvider(
        name="gcore",
        country="Luxembourg",
        tier="Tier 2",
        regions=["LU", "DE", "NL", "US", "SG"],
        free_tier=True,
        website="https://gcorelabs.com",
        api_url="https://api.gcorelabs.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="Gcore (لوكسمبورغ) - أوروبا وآسيا"
    ),
    # آسيا
    CloudProvider(
        name="naver_cloud",
        country="South Korea",
        tier="Tier 2",
        regions=["KR", "JP", "SG", "US"],
        free_tier=True,
        website="https://www.navercloudcorp.com",
        api_url="https://api.navercloudcorp.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="South Korea",
        auth_required=True,
        rate_limit=1000,
        notes="Naver Cloud (كوريا الجنوبية) - آسيا"
    ),
    CloudProvider(
        name="kakao_cloud",
        country="South Korea",
        tier="Tier 2",
        regions=["KR-Central", "KR-South"],
        free_tier=False,
        website="https://cloud.kakao.com",
        api_url="https://api.cloud.kakao.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="South Korea",
        auth_required=True,
        rate_limit=500,
        notes="Kakao Cloud (كوريا الجنوبية) - كوريا فقط"
    ),
    CloudProvider(
        name="sakura_cloud",
        country="Japan",
        tier="Tier 2",
        regions=["JP-Tokyo", "JP-Osaka", "JP-Ishikari"],
        free_tier=True,
        website="https://cloud.sakura.ad.jp",
        api_url="https://secure.sakura.ad.jp/cloud/zone",
        vpn_required=True,
        region_specific=True,
        vpn_country="Japan",
        auth_required=True,
        rate_limit=1000,
        notes="Sakura Cloud (اليابان) - اليابان فقط"
    ),
    CloudProvider(
        name="ntt_communications",
        country="Japan",
        tier="Tier 2",
        regions=["JP", "US", "UK", "DE", "SG", "AU"],
        free_tier=False,
        website="https://www.ntt.com",
        api_url="https://api.cloud.ntt.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="NTT Communications (اليابان) - عالمي"
    ),
    CloudProvider(
        name="softlayer",
        country="Japan",
        tier="Tier 2",
        regions=["JP-Tokyo", "JP-Osaka", "US-Dallas", "US-Washington"],
        free_tier=False,
        website="https://www.softlayer.com",
        api_url="https://api.softlayer.com",
        vpn_required=False,
        region_specific=False,
        auth_required=True,
        rate_limit=1000,
        notes="SoftLayer (IBM) - آسيا والولايات المتحدة"
    ),
    # الهند
    CloudProvider(
        name="reliance_jio",
        country="India",
        tier="Tier 2",
        regions=["IN-Mumbai", "IN-Delhi", "IN-Bangalore"],
        free_tier=False,
        website="https://cloud.jio.com",
        api_url="https://api.cloud.jio.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="India",
        auth_required=True,
        rate_limit=500,
        notes="Reliance Jio (الهند) - الهند فقط"
    ),
    CloudProvider(
        name="airtel_cloud",
        country="India",
        tier="Tier 2",
        regions=["IN-North", "IN-South", "IN-West", "IN-East"],
        free_tier=False,
        website="https://www.airtel.in/cloud",
        api_url="https://api.cloud.airtel.in",
        vpn_required=True,
        region_specific=True,
        vpn_country="India",
        auth_required=True,
        rate_limit=500,
        notes="Airtel Cloud (الهند) - الهند فقط"
    ),
    # جنوب شرق آسيا
    CloudProvider(
        name="exabytes",
        country="Malaysia",
        tier="Tier 2",
        regions=["MY-Kuala Lumpur", "SG-Singapore", "ID-Jakarta"],
        free_tier=True,
        website="https://www.exabytes.com",
        api_url="https://api.exabytes.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Malaysia",
        auth_required=True,
        rate_limit=1000,
        notes="Exabytes (ماليزيا) - جنوب شرق آسيا"
    ),
    CloudProvider(
        name="dimension_data",
        country="South Africa",
        tier="Tier 2",
        regions=["ZA-Johannesburg", "ZA-Cape Town"],
        free_tier=False,
        website="https://www.dimensiondata.com",
        api_url="https://api.cloud.dimensiondata.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="South Africa",
        auth_required=True,
        rate_limit=500,
        notes="Dimension Data (جنوب أفريقيا) - أفريقيا"
    ),
]

# ============================================================================
# TIER 3: مزودون محليون (يعملون في دولة واحدة فقط)
# ============================================================================

# أمريكا الشمالية
TIER_3_NORTH_AMERICA = [
    # كندا
    CloudProvider(
        name="telus_cloud",
        country="Canada",
        tier="Tier 3",
        regions=["CA-Toronto", "CA-Vancouver"],
        free_tier=False,
        website="https://www.telus.com/cloud",
        api_url="https://api.cloud.telus.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Canada",
        auth_required=True,
        rate_limit=500,
        notes="TELUS Cloud (كندا) - كندا فقط"
    ),
    CloudProvider(
        name="bell_cloud",
        country="Canada",
        tier="Tier 3",
        regions=["CA-Montreal", "CA-Toronto"],
        free_tier=False,
        website="https://cloud.bell.ca",
        api_url="https://api.cloud.bell.ca",
        vpn_required=True,
        region_specific=True,
        vpn_country="Canada",
        auth_required=True,
        rate_limit=500,
        notes="Bell Cloud (كندا) - كندا فقط"
    ),
    # المكسيك
    CloudProvider(
        name="telmex_cloud",
        country="Mexico",
        tier="Tier 3",
        regions=["MX-Mexico City", "MX-Monterrey"],
        free_tier=False,
        website="https://www.telmex.com/cloud",
        api_url="https://api.cloud.telmex.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Mexico",
        auth_required=True,
        rate_limit=500,
        notes="Telmex Cloud (المكسيك) - المكسيك فقط"
    ),
    CloudProvider(
        name="azteca_cloud",
        country="Mexico",
        tier="Tier 3",
        regions=["MX-Mexico City"],
        free_tier=False,
        website="https://www.azteca.net/cloud",
        api_url="https://api.cloud.azteca.net",
        vpn_required=True,
        region_specific=True,
        vpn_country="Mexico",
        auth_required=True,
        rate_limit=500,
        notes="Azteca Cloud (المكسيك) - المكسيك فقط"
    ),
]

# أمريكا الجنوبية
TIER_3_SOUTH_AMERICA = [
    # البرازيل
    CloudProvider(
        name="locaweb",
        country="Brazil",
        tier="Tier 3",
        regions=["BR-Sao Paulo", "BR-Rio de Janeiro"],
        free_tier=True,
        website="https://www.locaweb.com.br",
        api_url="https://api.locaweb.com.br",
        vpn_required=True,
        region_specific=True,
        vpn_country="Brazil",
        auth_required=True,
        rate_limit=1000,
        notes="Locaweb (البرازيل) - البرازيل فقط"
    ),
    CloudProvider(
        name="uol_cloud",
        country="Brazil",
        tier="Tier 3",
        regions=["BR-Sao Paulo"],
        free_tier=False,
        website="https://cloud.uol.com.br",
        api_url="https://api.cloud.uol.com.br",
        vpn_required=True,
        region_specific=True,
        vpn_country="Brazil",
        auth_required=True,
        rate_limit=500,
        notes="UOL Cloud (البرازيل) - البرازيل فقط"
    ),
    CloudProvider(
        name="algar_cloud",
        country="Brazil",
        tier="Tier 3",
        regions=["BR-Sao Paulo"],
        free_tier=False,
        website="https://www.algar.com.br/cloud",
        api_url="https://api.cloud.algar.com.br",
        vpn_required=True,
        region_specific=True,
        vpn_country="Brazil",
        auth_required=True,
        rate_limit=500,
        notes="Algar Cloud (البرازيل) - البرازيل فقط"
    ),
    # الأرجنتين
    CloudProvider(
        name="telefonica_cloud_ar",
        country="Argentina",
        tier="Tier 3",
        regions=["AR-Buenos Aires"],
        free_tier=False,
        website="https://www.telefonica.com.ar/cloud",
        api_url="https://api.cloud.telefonica.com.ar",
        vpn_required=True,
        region_specific=True,
        vpn_country="Argentina",
        auth_required=True,
        rate_limit=500,
        notes="Telefonica Cloud (الأرجنتين) - الأرجنتين فقط"
    ),
    # تشيلي
    CloudProvider(
        name="entel_cloud",
        country="Chile",
        tier="Tier 3",
        regions=["CL-Santiago"],
        free_tier=False,
        website="https://www.entel.cl/cloud",
        api_url="https://api.cloud.entel.cl",
        vpn_required=True,
        region_specific=True,
        vpn_country="Chile",
        auth_required=True,
        rate_limit=500,
        notes="Entel Cloud (تشيلي) - تشيلي فقط"
    ),
    # كولومبيا
    CloudProvider(
        name="claro_cloud",
        country="Colombia",
        tier="Tier 3",
        regions=["CO-Bogota"],
        free_tier=False,
        website="https://www.claro.com.co/cloud",
        api_url="https://api.cloud.claro.com.co",
        vpn_required=True,
        region_specific=True,
        vpn_country="Colombia",
        auth_required=True,
        rate_limit=500,
        notes="Claro Cloud (كولومبيا) - كولومبيا فقط"
    ),
]

# أوروبا
TIER_3_EUROPE = [
    # المملكة المتحدة
    CloudProvider(
        name="ukfast",
        country="United Kingdom",
        tier="Tier 3",
        regions=["GB-Manchester", "GB-London"],
        free_tier=False,
        website="https://www.ukfast.co.uk",
        api_url="https://api.ukfast.co.uk",
        vpn_required=True,
        region_specific=True,
        vpn_country="United Kingdom",
        auth_required=True,
        rate_limit=500,
        notes="UKFast (المملكة المتحدة) - المملكة المتحدة فقط"
    ),
    # روسيا
    CloudProvider(
        name="yandex_cloud",
        country="Russia",
        tier="Tier 3",
        regions=["ru-central1", "ru-west1", "ru-east1"],
        free_tier=True,
        website="https://cloud.yandex.com",
        api_url="https://api.cloud.yandex.net",
        vpn_required=True,
        region_specific=True,
        vpn_country="Russia",
        auth_required=True,
        rate_limit=1000,
        notes="Yandex Cloud (روسيا) - روسيا فقط - يتطلب VPN لروسيا"
    ),
    CloudProvider(
        name="sbercloud",
        country="Russia",
        tier="Tier 3",
        regions=["ru-moscow-1", "ru-moscow-2"],
        free_tier=False,
        website="https://sbercloud.ru",
        api_url="https://api.sbercloud.ru",
        vpn_required=True,
        region_specific=True,
        vpn_country="Russia",
        auth_required=True,
        rate_limit=500,
        notes="SberCloud (روسيا) - روسيا فقط - يتطلب VPN لروسيا"
    ),
    # تركيا
    CloudProvider(
        name="turkcell_cloud",
        country="Turkey",
        tier="Tier 3",
        regions=["TR-Istanbul", "TR-Ankara"],
        free_tier=False,
        website="https://www.turkcell.com.tr/cloud",
        api_url="https://api.cloud.turkcell.com.tr",
        vpn_required=True,
        region_specific=True,
        vpn_country="Turkey",
        auth_required=True,
        rate_limit=500,
        notes="Turkcell Cloud (تركيا) - تركيا فقط"
    ),
    CloudProvider(
        name="turknet_cloud",
        country="Turkey",
        tier="Tier 3",
        regions=["TR-Istanbul"],
        free_tier=False,
        website="https://www.turk.net/cloud",
        api_url="https://api.cloud.turk.net",
        vpn_required=True,
        region_specific=True,
        vpn_country="Turkey",
        auth_required=True,
        rate_limit=500,
        notes="TurkNet Cloud (تركيا) - تركيا فقط"
    ),
    # هولندا
    CloudProvider(
        name="transip_cloud",
        country="Netherlands",
        tier="Tier 3",
        regions=["NL-Amsterdam"],
        free_tier=False,
        website="https://www.transip.nl/cloud",
        api_url="https://api.transip.nl",
        vpn_required=True,
        region_specific=True,
        vpn_country="Netherlands",
        auth_required=True,
        rate_limit=500,
        notes="TransIP Cloud (هولندا) - هولندا فقط"
    ),
    # السويد
    CloudProvider(
        name="bahnholf_cloud",
        country="Sweden",
        tier="Tier 3",
        regions=["SE-Stockholm"],
        free_tier=False,
        website="https://www.bahnholf.se/cloud",
        api_url="https://api.cloud.bahnholf.se",
        vpn_required=True,
        region_specific=True,
        vpn_country="Sweden",
        auth_required=True,
        rate_limit=500,
        notes="Bahnholf Cloud (السويد) - السويد فقط"
    ),
    # النرويج
    CloudProvider(
        name="basefarm_cloud",
        country="Norway",
        tier="Tier 3",
        regions=["NO-Oslo"],
        free_tier=False,
        website="https://www.basefarm.com",
        api_url="https://api.basefarm.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Norway",
        auth_required=True,
        rate_limit=500,
        notes="Basefarm Cloud (النرويج) - النرويج فقط"
    ),
    # الدنمارك
    CloudProvider(
        name="siminn_cloud",
        country="Denmark",
        tier="Tier 3",
        regions=["DK-Copenhagen"],
        free_tier=False,
        website="https://www.siminn.dk/cloud",
        api_url="https://api.cloud.siminn.dk",
        vpn_required=True,
        region_specific=True,
        vpn_country="Denmark",
        auth_required=True,
        rate_limit=500,
        notes="Siminn Cloud (الدانمرك) - الدنمارك فقط"
    ),
    # فنلندا
    CloudProvider(
        name="elisa_cloud",
        country="Finland",
        tier="Tier 3",
        regions=["FI-Helsinki"],
        free_tier=False,
        website="https://www.elisa.fi/cloud",
        api_url="https://api.cloud.elisa.fi",
        vpn_required=True,
        region_specific=True,
        vpn_country="Finland",
        auth_required=True,
        rate_limit=500,
        notes="Elisa Cloud (فنلندا) - فنلندا فقط"
    ),
    # بولندا
    CloudProvider(
        name="home_cloud",
        country="Poland",
        tier="Tier 3",
        regions=["PL-Warsaw"],
        free_tier=True,
        website="https://home.pl/cloud",
        api_url="https://api.cloud.home.pl",
        vpn_required=True,
        region_specific=True,
        vpn_country="Poland",
        auth_required=True,
        rate_limit=1000,
        notes="Home Cloud (بولندا) - بولندا فقط"
    ),
    # المجر
    CloudProvider(
        name="t_home_cloud",
        country="Hungary",
        tier="Tier 3",
        regions=["HU-Budapest"],
        free_tier=False,
        website="https://www.t-home.hu/cloud",
        api_url="https://api.cloud.t-home.hu",
        vpn_required=True,
        region_specific=True,
        vpn_country="Hungary",
        auth_required=True,
        rate_limit=500,
        notes="T-Home Cloud (المجر) - المجر فقط"
    ),
    # رومانيا
    CloudProvider(
        name="ipserverone",
        country="Romania",
        tier="Tier 3",
        regions=["RO-Bucharest"],
        free_tier=True,
        website="https://www.ipserverone.com",
        api_url="https://api.ipserverone.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Romania",
        auth_required=True,
        rate_limit=1000,
        notes="IPServerOne (رومانيا) - رومانيا فقط"
    ),
    # بلغاريا
    CloudProvider(
        name="storpool",
        country="Bulgaria",
        tier="Tier 3",
        regions=["BG-Sofia"],
        free_tier=True,
        website="https://www.storpool.com",
        api_url="https://api.storpool.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Bulgaria",
        auth_required=True,
        rate_limit=1000,
        notes="StorPool (بلغاريا) - بلغاريا فقط"
    ),
    # صربيا
    CloudProvider(
        name="serbia_cloud",
        country="Serbia",
        tier="Tier 3",
        regions=["RS-Belgrade"],
        free_tier=False,
        website="https://www.serbia-cloud.rs",
        api_url="https://api.serbia-cloud.rs",
        vpn_required=True,
        region_specific=True,
        vpn_country="Serbia",
        auth_required=True,
        rate_limit=500,
        notes="Serbia Cloud (صربيا) - صربيا فقط"
    ),
]

# آسيا
TIER_3_ASIA = [
    # الهند
    CloudProvider(
        name="netmagic",
        country="India",
        tier="Tier 3",
        regions=["IN-Mumbai", "IN-Bangalore", "IN-Delhi"],
        free_tier=False,
        website="https://www.netmagic.net",
        api_url="https://api.netmagic.net",
        vpn_required=True,
        region_specific=True,
        vpn_country="India",
        auth_required=True,
        rate_limit=500,
        notes="NetMagic (الهند) - الهند فقط"
    ),
    CloudProvider(
        name="esds",
        country="India",
        tier="Tier 3",
        regions=["IN-Mumbai", "IN-Pune"],
        free_tier=False,
        website="https://www.esds.co.in",
        api_url="https://api.esds.co.in",
        vpn_required=True,
        region_specific=True,
        vpn_country="India",
        auth_required=True,
        rate_limit=500,
        notes="ESDS (الهند) - الهند فقط"
    ),
    # إندونيسيا
    CloudProvider(
        name="izoo_cloud",
        country="Indonesia",
        tier="Tier 3",
        regions=["ID-Jakarta"],
        free_tier=False,
        website="https://www.izoo.id",
        api_url="https://api.izoo.id",
        vpn_required=True,
        region_specific=True,
        vpn_country="Indonesia",
        auth_required=True,
        rate_limit=500,
        notes="iZoo Cloud (إندونيسيا) - إندونيسيا فقط"
    ),
    CloudProvider(
        name="cbn_cloud",
        country="Indonesia",
        tier="Tier 3",
        regions=["ID-Jakarta"],
        free_tier=False,
        website="https://www.cbn.net.id/cloud",
        api_url="https://api.cloud.cbn.net.id",
        vpn_required=True,
        region_specific=True,
        vpn_country="Indonesia",
        auth_required=True,
        rate_limit=500,
        notes="CBN Cloud (إندونيسيا) - إندونيسيا فقط"
    ),
    # ماليزيا
    CloudProvider(
        name="aims_cloud",
        country="Malaysia",
        tier="Tier 3",
        regions=["MY-Kuala Lumpur"],
        free_tier=False,
        website="https://www.aims.com.my",
        api_url="https://api.aims.com.my",
        vpn_required=True,
        region_specific=True,
        vpn_country="Malaysia",
        auth_required=True,
        rate_limit=500,
        notes="AIMS Cloud (ماليزيا) - ماليزيا فقط"
    ),
    # تايلاند
    CloudProvider(
        name="tcc_cloud",
        country="Thailand",
        tier="Tier 3",
        regions=["TH-Bangkok"],
        free_tier=False,
        website="https://www.tcc.co.th/cloud",
        api_url="https://api.cloud.tcc.co.th",
        vpn_required=True,
        region_specific=True,
        vpn_country="Thailand",
        auth_required=True,
        rate_limit=500,
        notes="TCC Cloud (تايلاند) - تايلاند فقط"
    ),
    CloudProvider(
        name="trueidc_cloud",
        country="Thailand",
        tier="Tier 3",
        regions=["TH-Bangkok"],
        free_tier=False,
        website="https://www.trueidc.com",
        api_url="https://api.trueidc.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Thailand",
        auth_required=True,
        rate_limit=500,
        notes="TrueIDC Cloud (تايلاند) - تايلاند فقط"
    ),
    # فيتنام
    CloudProvider(
        name="viettel_cloud",
        country="Vietnam",
        tier="Tier 3",
        regions=["VN-Hanoi", "VN-Ho Chi Minh"],
        free_tier=True,
        website="https://viettelcloud.vn",
        api_url="https://api.viettelcloud.vn",
        vpn_required=True,
        region_specific=True,
        vpn_country="Vietnam",
        auth_required=True,
        rate_limit=1000,
        notes="Viettel Cloud (فيتنام) - فيتنام فقط"
    ),
    CloudProvider(
        name="vnpt_cloud",
        country="Vietnam",
        tier="Tier 3",
        regions=["VN-Hanoi"],
        free_tier=False,
        website="https://vnptcloud.vn",
        api_url="https://api.vnptcloud.vn",
        vpn_required=True,
        region_specific=True,
        vpn_country="Vietnam",
        auth_required=True,
        rate_limit=500,
        notes="VNPT Cloud (فيتنام) - فيتنام فقط"
    ),
    # الفلبين
    CloudProvider(
        name="globe_cloud",
        country="Philippines",
        tier="Tier 3",
        regions=["PH-Manila"],
        free_tier=False,
        website="https://www.globe.com.ph/cloud",
        api_url="https://api.cloud.globe.com.ph",
        vpn_required=True,
        region_specific=True,
        vpn_country="Philippines",
        auth_required=True,
        rate_limit=500,
        notes="Globe Cloud (الفلبين) - الفلبين فقط"
    ),
    CloudProvider(
        name="pldt_cloud",
        country="Philippines",
        tier="Tier 3",
        regions=["PH-Manila"],
        free_tier=False,
        website="https://www.pldt.com/cloud",
        api_url="https://api.cloud.pldt.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Philippines",
        auth_required=True,
        rate_limit=500,
        notes="PLDT Cloud (الفلبين) - الفلبين فقط"
    ),
]

# أفريقيا
TIER_3_AFRICA = [
    # جنوب أفريقيا
    CloudProvider(
        name="afrihost_cloud",
        country="South Africa",
        tier="Tier 3",
        regions=["ZA-Johannesburg", "ZA-Cape Town"],
        free_tier=True,
        website="https://www.afrihost.com",
        api_url="https://api.afrihost.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="South Africa",
        auth_required=True,
        rate_limit=1000,
        notes="AfriHost Cloud (جنوب أفريقيا) - جنوب أفريقيا فقط"
    ),
    CloudProvider(
        name="hetzner_za",
        country="South Africa",
        tier="Tier 3",
        regions=["ZA-Johannesburg"],
        free_tier=False,
        website="https://www.hetzner.co.za",
        api_url="https://api.hetzner.co.za",
        vpn_required=True,
        region_specific=True,
        vpn_country="South Africa",
        auth_required=True,
        rate_limit=500,
        notes="Hetzner South Africa - جنوب أفريقيا فقط"
    ),
    CloudProvider(
        name="xneelo",
        country="South Africa",
        tier="Tier 3",
        regions=["ZA-Johannesburg"],
        free_tier=True,
        website="https://www.xneelo.co.za",
        api_url="https://api.xneelo.co.za",
        vpn_required=True,
        region_specific=True,
        vpn_country="South Africa",
        auth_required=True,
        rate_limit=1000,
        notes="xneelo (جنوب أفريقيا) - جنوب أفريقيا فقط"
    ),
    # نيجيريا
    CloudProvider(
        name="mainone_cloud",
        country="Nigeria",
        tier="Tier 3",
        regions=["NG-Lagos"],
        free_tier=False,
        website="https://www.mainone.net",
        api_url="https://api.mainone.net",
        vpn_required=True,
        region_specific=True,
        vpn_country="Nigeria",
        auth_required=True,
        rate_limit=500,
        notes="MainOne Cloud (نيجيريا) - نيجيريا فقط"
    ),
    CloudProvider(
        name="mtn_cloud_ng",
        country="Nigeria",
        tier="Tier 3",
        regions=["NG-Lagos"],
        free_tier=False,
        website="https://www.mtn.ng/cloud",
        api_url="https://api.cloud.mtn.ng",
        vpn_required=True,
        region_specific=True,
        vpn_country="Nigeria",
        auth_required=True,
        rate_limit=500,
        notes="MTN Cloud (نيجيريا) - نيجيريا فقط"
    ),
    # كينيا
    CloudProvider(
        name="safaricom_cloud",
        country="Kenya",
        tier="Tier 3",
        regions=["KE-Nairobi"],
        free_tier=False,
        website="https://www.safaricom.co.ke/cloud",
        api_url="https://api.cloud.safaricom.co.ke",
        vpn_required=True,
        region_specific=True,
        vpn_country="Kenya",
        auth_required=True,
        rate_limit=500,
        notes="Safaricom Cloud (كينيا) - كينيا فقط"
    ),
    CloudProvider(
        name="liquid_telecom",
        country="Kenya",
        tier="Tier 3",
        regions=["KE-Nairobi"],
        free_tier=False,
        website="https://www.liquidtelecom.com",
        api_url="https://api.liquidtelecom.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Kenya",
        auth_required=True,
        rate_limit=500,
        notes="Liquid Telecom (كينيا) - كينيا فقط"
    ),
    # مصر
    CloudProvider(
        name="orange_eg",
        country="Egypt",
        tier="Tier 3",
        regions=["EG-Cairo", "EG-Alexandria"],
        free_tier=True,
        website="https://www.orange.eg",
        api_url="https://api.orange.eg",
        vpn_required=True,
        region_specific=True,
        vpn_country="Egypt",
        auth_required=True,
        rate_limit=1000,
        notes="Orange Egypt - مصر فقط"
    ),
    CloudProvider(
        name="etisalat_eg",
        country="Egypt",
        tier="Tier 3",
        regions=["EG-Cairo"],
        free_tier=False,
        website="https://www.etisalat.eg",
        api_url="https://api.etisalat.eg",
        vpn_required=True,
        region_specific=True,
        vpn_country="Egypt",
        auth_required=True,
        rate_limit=500,
        notes="Etisalat Egypt - مصر فقط"
    ),
    CloudProvider(
        name="vodafone_eg",
        country="Egypt",
        tier="Tier 3",
        regions=["EG-Cairo"],
        free_tier=False,
        website="https://www.vodafone.eg",
        api_url="https://api.vodafone.eg",
        vpn_required=True,
        region_specific=True,
        vpn_country="Egypt",
        auth_required=True,
        rate_limit=500,
        notes="Vodafone Egypt - مصر فقط"
    ),
    CloudProvider(
        name="we_cloud_eg",
        country="Egypt",
        tier="Tier 3",
        regions=["EG-Cairo"],
        free_tier=False,
        website="https://www.we.eg",
        api_url="https://api.we.eg",
        vpn_required=True,
        region_specific=True,
        vpn_country="Egypt",
        auth_required=True,
        rate_limit=500,
        notes="WE Egypt - مصر فقط"
    ),
    # المغرب
    CloudProvider(
        name="maroc_telecom",
        country="Morocco",
        tier="Tier 3",
        regions=["MA-Casablanca", "MA-Rabat"],
        free_tier=False,
        website="https://www.iam.net.ma",
        api_url="https://api.iam.net.ma",
        vpn_required=True,
        region_specific=True,
        vpn_country="Morocco",
        auth_required=True,
        rate_limit=500,
        notes="Maroc Telecom - المغرب فقط"
    ),
    CloudProvider(
        name="inwi",
        country="Morocco",
        tier="Tier 3",
        regions=["MA-Casablanca"],
        free_tier=False,
        website="https://www.inwi.ma",
        api_url="https://api.inwi.ma",
        vpn_required=True,
        region_specific=True,
        vpn_country="Morocco",
        auth_required=True,
        rate_limit=500,
        notes="Inwi - المغرب فقط"
    ),
    # الجزائر
    CloudProvider(
        name="djezzy",
        country="Algeria",
        tier="Tier 3",
        regions=["DZ-Algiers"],
        free_tier=False,
        website="https://www.djezzy.dz",
        api_url="https://api.djezzy.dz",
        vpn_required=True,
        region_specific=True,
        vpn_country="Algeria",
        auth_required=True,
        rate_limit=500,
        notes="Djezzy - الجزائر فقط"
    ),
    CloudProvider(
        name="mobilis",
        country="Algeria",
        tier="Tier 3",
        regions=["DZ-Algiers"],
        free_tier=False,
        website="https://www.mobilis.dz",
        api_url="https://api.mobilis.dz",
        vpn_required=True,
        region_specific=True,
        vpn_country="Algeria",
        auth_required=True,
        rate_limit=500,
        notes="Mobilis - الجزائر فقط"
    ),
    # تونس
    CloudProvider(
        name="ooredoo_tn",
        country="Tunisia",
        tier="Tier 3",
        regions=["TN-Tunis"],
        free_tier=False,
        website="https://www.ooredoo.tn",
        api_url="https://api.ooredoo.tn",
        vpn_required=True,
        region_specific=True,
        vpn_country="Tunisia",
        auth_required=True,
        rate_limit=500,
        notes="Ooredoo Tunisia - تونس فقط"
    ),
    CloudProvider(
        name="topnet",
        country="Tunisia",
        tier="Tier 3",
        regions=["TN-Tunis"],
        free_tier=False,
        website="https://www.topnet.tn",
        api_url="https://api.topnet.tn",
        vpn_required=True,
        region_specific=True,
        vpn_country="Tunisia",
        auth_required=True,
        rate_limit=500,
        notes="TopNet - تونس فقط"
    ),
]

# الشرق الأوسط
TIER_3_MIDDLE_EAST = [
    # السعودية
    CloudProvider(
        name="stc_cloud",
        country="Saudi Arabia",
        tier="Tier 3",
        regions=["SA-Riyadh", "SA-Jeddah", "SA-Dammam"],
        free_tier=True,
        website="https://cloud.stc.com.sa",
        api_url="https://api.cloud.stc.com.sa",
        vpn_required=True,
        region_specific=True,
        vpn_country="Saudi Arabia",
        auth_required=True,
        rate_limit=1000,
        notes="STC Cloud (السعودية) - السعودية فقط"
    ),
    CloudProvider(
        name="mobily_cloud",
        country="Saudi Arabia",
        tier="Tier 3",
        regions=["SA-Riyadh", "SA-Jeddah"],
        free_tier=False,
        website="https://www.mobily.com.sa/cloud",
        api_url="https://api.cloud.mobily.com.sa",
        vpn_required=True,
        region_specific=True,
        vpn_country="Saudi Arabia",
        auth_required=True,
        rate_limit=500,
        notes="Mobily Cloud (السعودية) - السعودية فقط"
    ),
    CloudProvider(
        name="zain_sa",
        country="Saudi Arabia",
        tier="Tier 3",
        regions=["SA-Riyadh", "SA-Jeddah"],
        free_tier=False,
        website="https://www.zain.com.sa",
        api_url="https://api.zain.com.sa",
        vpn_required=True,
        region_specific=True,
        vpn_country="Saudi Arabia",
        auth_required=True,
        rate_limit=500,
        notes="Zain Saudi Arabia - السعودية فقط"
    ),
    # الإمارات
    CloudProvider(
        name="etisalat_cloud",
        country="United Arab Emirates",
        tier="Tier 3",
        regions=["AE-Dubai", "AE-Abu Dhabi"],
        free_tier=True,
        website="https://www.etisalat.ae/cloud",
        api_url="https://api.cloud.etisalat.ae",
        vpn_required=True,
        region_specific=True,
        vpn_country="United Arab Emirates",
        auth_required=True,
        rate_limit=1000,
        notes="Etisalat Cloud (الإمارات) - الإمارات فقط"
    ),
    CloudProvider(
        name="du_cloud",
        country="United Arab Emirates",
        tier="Tier 3",
        regions=["AE-Dubai"],
        free_tier=False,
        website="https://www.du.ae/cloud",
        api_url="https://api.cloud.du.ae",
        vpn_required=True,
        region_specific=True,
        vpn_country="United Arab Emirates",
        auth_required=True,
        rate_limit=500,
        notes="du Cloud (الإمارات) - الإمارات فقط"
    ),
    # قطر
    CloudProvider(
        name="ooredoo_qa",
        country="Qatar",
        tier="Tier 3",
        regions=["QA-Doha"],
        free_tier=True,
        website="https://www.ooredoo.qa",
        api_url="https://api.ooredoo.qa",
        vpn_required=True,
        region_specific=True,
        vpn_country="Qatar",
        auth_required=True,
        rate_limit=1000,
        notes="Ooredoo Qatar - قطر فقط"
    ),
    CloudProvider(
        name="vodafone_qa",
        country="Qatar",
        tier="Tier 3",
        regions=["QA-Doha"],
        free_tier=False,
        website="https://www.vodafone.qa",
        api_url="https://api.vodafone.qa",
        vpn_required=True,
        region_specific=True,
        vpn_country="Qatar",
        auth_required=True,
        rate_limit=500,
        notes="Vodafone Qatar - قطر فقط"
    ),
    # الكويت
    CloudProvider(
        name="zain_kw",
        country="Kuwait",
        tier="Tier 3",
        regions=["KW-Kuwait City"],
        free_tier=False,
        website="https://www.zain.com",
        api_url="https://api.zain.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Kuwait",
        auth_required=True,
        rate_limit=500,
        notes="Zain Kuwait - الكويت فقط"
    ),
    CloudProvider(
        name="ooredoo_kw",
        country="Kuwait",
        tier="Tier 3",
        regions=["KW-Kuwait City"],
        free_tier=False,
        website="https://www.ooredoo.com.kw",
        api_url="https://api.ooredoo.com.kw",
        vpn_required=True,
        region_specific=True,
        vpn_country="Kuwait",
        auth_required=True,
        rate_limit=500,
        notes="Ooredoo Kuwait - الكويت فقط"
    ),
    # عمان
    CloudProvider(
        name="omantel_cloud",
        country="Oman",
        tier="Tier 3",
        regions=["OM-Muscat"],
        free_tier=False,
        website="https://www.omantel.om",
        api_url="https://api.omantel.om",
        vpn_required=True,
        region_specific=True,
        vpn_country="Oman",
        auth_required=True,
        rate_limit=500,
        notes="Omantel Cloud - عمان فقط"
    ),
    CloudProvider(
        name="ooredoo_om",
        country="Oman",
        tier="Tier 3",
        regions=["OM-Muscat"],
        free_tier=False,
        website="https://www.ooredoo.om",
        api_url="https://api.ooredoo.om",
        vpn_required=True,
        region_specific=True,
        vpn_country="Oman",
        auth_required=True,
        rate_limit=500,
        notes="Ooredoo Oman - عمان فقط"
    ),
    # البحرين
    CloudProvider(
        name="batelco_cloud",
        country="Bahrain",
        tier="Tier 3",
        regions=["BH-Manama"],
        free_tier=False,
        website="https://www.batelco.com",
        api_url="https://api.batelco.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Bahrain",
        auth_required=True,
        rate_limit=500,
        notes="Batelco Cloud - البحرين فقط"
    ),
    CloudProvider(
        name="zain_bh",
        country="Bahrain",
        tier="Tier 3",
        regions=["BH-Manama"],
        free_tier=False,
        website="https://www.bh.zain.com",
        api_url="https://api.bh.zain.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Bahrain",
        auth_required=True,
        rate_limit=500,
        notes="Zain Bahrain - البحرين فقط"
    ),
    # الأردن
    CloudProvider(
        name="orange_jo",
        country="Jordan",
        tier="Tier 3",
        regions=["JO-Amman"],
        free_tier=False,
        website="https://www.orange.jo",
        api_url="https://api.orange.jo",
        vpn_required=True,
        region_specific=True,
        vpn_country="Jordan",
        auth_required=True,
        rate_limit=500,
        notes="Orange Jordan - الأردن فقط"
    ),
    CloudProvider(
        name="zain_jo",
        country="Jordan",
        tier="Tier 3",
        regions=["JO-Amman"],
        free_tier=False,
        website="https://www.jo.zain.com",
        api_url="https://api.jo.zain.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Jordan",
        auth_required=True,
        rate_limit=500,
        notes="Zain Jordan - الأردن فقط"
    ),
    # لبنان
    CloudProvider(
        name="touch",
        country="Lebanon",
        tier="Tier 3",
        regions=["LB-Beirut"],
        free_tier=False,
        website="https://www.touch.com.lb",
        api_url="https://api.touch.com.lb",
        vpn_required=True,
        region_specific=True,
        vpn_country="Lebanon",
        auth_required=True,
        rate_limit=500,
        notes="Touch Lebanon - لبنان فقط"
    ),
    CloudProvider(
        name="alphacell",
        country="Lebanon",
        tier="Tier 3",
        regions=["LB-Beirut"],
        free_tier=False,
        website="https://www.alphacell.com.lb",
        api_url="https://api.alphacell.com.lb",
        vpn_required=True,
        region_specific=True,
        vpn_country="Lebanon",
        auth_required=True,
        rate_limit=500,
        notes="Alpha Cell - لبنان فقط"
    ),
    # العراق
    CloudProvider(
        name="asiacell",
        country="Iraq",
        tier="Tier 3",
        regions=["IQ-Baghdad", "IQ-Erbil"],
        free_tier=False,
        website="https://www.asiacell.com",
        api_url="https://api.asiacell.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Iraq",
        auth_required=True,
        rate_limit=500,
        notes="Asiacell - العراق فقط"
    ),
    CloudProvider(
        name="zain_iq",
        country="Iraq",
        tier="Tier 3",
        regions=["IQ-Baghdad"],
        free_tier=False,
        website="https://www.iq.zain.com",
        api_url="https://api.iq.zain.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Iraq",
        auth_required=True,
        rate_limit=500,
        notes="Zain Iraq - العراق فقط"
    ),
]

# أوقيانوسيا
TIER_3_OCEANIA = [
    # أستراليا
    CloudProvider(
        name="au_cloud",
        country="Australia",
        tier="Tier 3",
        regions=["AU-Sydney", "AU-Melbourne", "AU-Brisbane"],
        free_tier=True,
        website="https://www.aucloud.com.au",
        api_url="https://api.aucloud.com.au",
        vpn_required=True,
        region_specific=True,
        vpn_country="Australia",
        auth_required=True,
        rate_limit=1000,
        notes="AUCloud (أستراليا) - أستراليا فقط"
    ),
    CloudProvider(
        name="macquarie_cloud",
        country="Australia",
        tier="Tier 3",
        regions=["AU-Sydney", "AU-Canberra"],
        free_tier=False,
        website="https://www.macquariecloudservices.com",
        api_url="https://api.macquariecloudservices.com",
        vpn_required=True,
        region_specific=True,
        vpn_country="Australia",
        auth_required=True,
        rate_limit=500,
        notes="Macquarie Cloud (أستراليا) - أستراليا فقط"
    ),
    # نيوزيلندا
    CloudProvider(
        name="spark_cloud_nz",
        country="New Zealand",
        tier="Tier 3",
        regions=["NZ-Auckland", "NZ-Wellington"],
        free_tier=False,
        website="https://www.spark.co.nz/cloud",
        api_url="https://api.cloud.spark.co.nz",
        vpn_required=True,
        region_specific=True,
        vpn_country="New Zealand",
        auth_required=True,
        rate_limit=500,
        notes="Spark Cloud (نيوزيلندا) - نيوزيلندا فقط"
    ),
    CloudProvider(
        name="datacom_cloud",
        country="New Zealand",
        tier="Tier 3",
        regions=["NZ-Auckland"],
        free_tier=False,
        website="https://www.datacom.co.nz",
        api_url="https://api.datacom.co.nz",
        vpn_required=True,
        region_specific=True,
        vpn_country="New Zealand",
        auth_required=True,
        rate_limit=500,
        notes="Datacom Cloud (نيوزيلندا) - نيوزيلندا فقط"
    ),
]

# ============================================================================
# مزودون مجانيون (Free Tier Providers)
# ============================================================================

FREE_TIER_PROVIDERS = [
    # عالمي
    "aws", "google_cloud", "azure", "oracle_cloud",
    "digitalocean", "linode", "vultr", "hetzner_cloud",
    "ovhcloud", "scaleway", "upcloud",
    # آسيا
    "alibaba_cloud", "tencent_cloud", "huawei_cloud",
    "yandex_cloud", "viettel_cloud",
    # أوروبا
    "home_cloud", "storpool",
    # أفريقيا
    "afrihost_cloud", "xneelo",
    # الشرق الأوسط
    "stc_cloud", "etisalat_cloud", "ooredoo_qa",
]

# ============================================================================
# مزودون يتطلبون VPN
# ============================================================================

VPN_REQUIRED_PROVIDERS = {
    # الصين
    "alibaba_cloud": "China",
    "tencent_cloud": "China",
    "huawei_cloud": "China",
    "baidu_cloud": "China",
    # روسيا
    "yandex_cloud": "Russia",
    "sbercloud": "Russia",
    # كوريا الجنوبية
    "naver_cloud": "South Korea",
    "kakao_cloud": "South Korea",
    # اليابان
    "sakura_cloud": "Japan",
    # الهند
    "reliance_jio": "India",
    "airtel_cloud": "India",
    "netmagic": "India",
    "esds": "India",
    # إندونيسيا
    "izoo_cloud": "Indonesia",
    "cbn_cloud": "Indonesia",
    # ماليزيا
    "aims_cloud": "Malaysia",
    # تايلاند
    "tcc_cloud": "Thailand",
    "trueidc_cloud": "Thailand",
    # فيتنام
    "viettel_cloud": "Vietnam",
    "vnpt_cloud": "Vietnam",
    # الفلبين
    "globe_cloud": "Philippines",
    "pldt_cloud": "Philippines",
    # جنوب أفريقيا
    "afrihost_cloud": "South Africa",
    "hetzner_za": "South Africa",
    "xneelo": "South Africa",
    # نيجيريا
    "mainone_cloud": "Nigeria",
    "mtn_cloud_ng": "Nigeria",
    # كينيا
    "safaricom_cloud": "Kenya",
    "liquid_telecom": "Kenya",
    # مصر
    "orange_eg": "Egypt",
    "etisalat_eg": "Egypt",
    "vodafone_eg": "Egypt",
    "we_cloud_eg": "Egypt",
    # المغرب
    "maroc_telecom": "Morocco",
    "inwi": "Morocco",
    # الجزائر
    "djezzy": "Algeria",
    "mobilis": "Algeria",
    # تونس
    "ooredoo_tn": "Tunisia",
    "topnet": "Tunisia",
    # السعودية
    "stc_cloud": "Saudi Arabia",
    "mobily_cloud": "Saudi Arabia",
    "zain_sa": "Saudi Arabia",
    # الإمارات
    "etisalat_cloud": "United Arab Emirates",
    "du_cloud": "United Arab Emirates",
    # قطر
    "ooredoo_qa": "Qatar",
    "vodafone_qa": "Qatar",
    # الكويت
    "zain_kw": "Kuwait",
    "ooredoo_kw": "Kuwait",
    # عمان
    "omantel_cloud": "Oman",
    "ooredoo_om": "Oman",
    # البحرين
    "batelco_cloud": "Bahrain",
    "zain_bh": "Bahrain",
    # الأردن
    "orange_jo": "Jordan",
    "zain_jo": "Jordan",
    # لبنان
    "touch": "Lebanon",
    "alphacell": "Lebanon",
    # العراق
    "asiacell": "Iraq",
    "zain_iq": "Iraq",
    # تركيا
    "turkcell_cloud": "Turkey",
    "turknet_cloud": "Turkey",
    # كندا
    "telus_cloud": "Canada",
    "bell_cloud": "Canada",
    # المكسيك
    "telmex_cloud": "Mexico",
    "azteca_cloud": "Mexico",
    # البرازيل
    "locaweb": "Brazil",
    "uol_cloud": "Brazil",
    "algar_cloud": "Brazil",
    # الأرجنتين
    "telefonica_cloud_ar": "Argentina",
    # تشيلي
    "entel_cloud": "Chile",
    # كولومبيا
    "claro_cloud": "Colombia",
    # أستراليا
    "au_cloud": "Australia",
    "macquarie_cloud": "Australia",
    # نيوزيلندا
    "spark_cloud_nz": "New Zealand",
    "datacom_cloud": "New Zealand",
    # أوروبا (دول محددة)
    "lemonway": "France",
    "transip_cloud": "Netherlands",
    "bahnholf_cloud": "Sweden",
    "basefarm_cloud": "Norway",
    "siminn_cloud": "Denmark",
    "elisa_cloud": "Finland",
    "ionos": "Germany",
    # المملكة المتحدة
    "ukfast": "United Kingdom",
    # بولندا
    "home_cloud": "Poland",
    "t_home_cloud": "Hungary",
    # رومانيا
    "ipserverone": "Romania",
    # بلغاريا
    "storpool": "Bulgaria",
    # صربيا
    "serbia_cloud": "Serbia",
}

# ============================================================================
# وظائف مساعد
# ============================================================================


# --- EXTRA GLOBAL / REGIONAL CLOUDS (expand to 200+) ---
EXTRA_CLOUD_PROVIDERS = [
    CloudProvider(name="alibaba_intl", country="Singapore", tier="Tier 1", regions=["ap-southeast-1"], free_tier=True, website="https://www.alibabacloud.com", api_url="https://ecs.aliyuncs.com", vpn_required=False),
    CloudProvider(name="tencent_intl", country="Singapore", tier="Tier 1", regions=["ap-singapore"], free_tier=True, website="https://intl.cloud.tencent.com", api_url="https://cvm.tencentcloudapi.com", vpn_required=False),
    CloudProvider(name="huawei_intl", country="Singapore", tier="Tier 1", regions=["ap-southeast-1"], free_tier=True, website="https://www.huaweicloud.com", api_url="https://ecs.ap-southeast-1.myhuaweicloud.com", vpn_required=False),
    CloudProvider(name="aws_china", country="China", tier="Tier 1", regions=["cn-north-1","cn-northwest-1"], free_tier=False, website="https://www.amazonaws.cn", api_url="https://ec2.amazonaws.com.cn", vpn_required=True, vpn_country="China"),
    CloudProvider(name="azure_china", country="China", tier="Tier 1", regions=["chinaeast","chinanorth"], free_tier=False, website="https://www.azure.cn", api_url="https://management.chinacloudapi.cn", vpn_required=True, vpn_country="China"),
    CloudProvider(name="gcp_middle_east", country="UAE", tier="Tier 1", regions=["me-central1","me-west1"], free_tier=True, website="https://cloud.google.com", api_url="https://cloud.googleapis.com", vpn_required=False),
    CloudProvider(name="oracle_me", country="UAE", tier="Tier 1", regions=["me-dubai-1","me-jeddah-1"], free_tier=True, website="https://www.oracle.com/cloud", api_url="https://iaas.me-dubai-1.oraclecloud.com", vpn_required=False),
    CloudProvider(name="contabo", country="Germany", tier="Tier 2", regions=["EU","US","SIN","JPN","AUS"], free_tier=False, website="https://contabo.com", api_url="https://api.contabo.com", vpn_required=False),
    CloudProvider(name="netcup", country="Germany", tier="Tier 2", regions=["DE"], free_tier=False, website="https://www.netcup.eu", api_url="https://www.netcup-wiki.de", vpn_required=False),
    CloudProvider(name="time4vps", country="Lithuania", tier="Tier 2", regions=["EU"], free_tier=False, website="https://www.time4vps.com", api_url="https://billing.time4vps.com", vpn_required=False),
    CloudProvider(name="kamatera", country="Israel", tier="Tier 2", regions=["AS","EU","US","HK","AU"], free_tier=True, website="https://www.kamatera.com", api_url="https://console.kamatera.com", vpn_required=False),
    CloudProvider(name="atlantic_net", country="United States", tier="Tier 2", regions=["US","CA","UK","DE"], free_tier=False, website="https://www.atlantic.net", api_url="https://www.atlantic.net", vpn_required=False),
    CloudProvider(name="ramnode", country="United States", tier="Tier 2", regions=["US","NL"], free_tier=False, website="https://www.ramnode.com", api_url="https://www.ramnode.com", vpn_required=False),
    CloudProvider(name="buyvm", country="United States", tier="Tier 2", regions=["US","LU"], free_tier=False, website="https://buyvm.net", api_url="https://buyvm.net", vpn_required=False),
    CloudProvider(name="hosthatch", country="United States", tier="Tier 2", regions=["US","EU","ASIA","AU"], free_tier=False, website="https://hosthatch.com", api_url="https://hosthatch.com", vpn_required=False),
    CloudProvider(name="virmach", country="United States", tier="Tier 2", regions=["US"], free_tier=False, website="https://virmach.com", api_url="https://virmach.com", vpn_required=False),
    CloudProvider(name="racknerd", country="United States", tier="Tier 2", regions=["US"], free_tier=False, website="https://www.racknerd.com", api_url="https://www.racknerd.com", vpn_required=False),
    CloudProvider(name="alphavps", country="Bulgaria", tier="Tier 2", regions=["EU","US"], free_tier=False, website="https://www.alphavps.com", api_url="https://www.alphavps.com", vpn_required=False),
    CloudProvider(name="pq_hosting", country="Estonia", tier="Tier 2", regions=["EU","US","ASIA"], free_tier=False, website="https://pq.hosting", api_url="https://pq.hosting", vpn_required=False),
    CloudProvider(name="firstvds", country="Russia", tier="Tier 3", regions=["RU"], free_tier=False, website="https://firstvds.ru", api_url="https://firstvds.ru", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="selectel", country="Russia", tier="Tier 2", regions=["RU"], free_tier=False, website="https://selectel.ru", api_url="https://api.selectel.ru", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="yandex_cloud", country="Russia", tier="Tier 1", regions=["ru-central1"], free_tier=True, website="https://cloud.yandex.com", api_url="https://api.cloud.yandex.net", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="mailru_cloud", country="Russia", tier="Tier 2", regions=["RU"], free_tier=True, website="https://cloud.mail.ru", api_url="https://cloud.mail.ru", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="vk_cloud", country="Russia", tier="Tier 2", regions=["RU"], free_tier=True, website="https://cloud.vk.com", api_url="https://cloud.vk.com", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="reg_ru", country="Russia", tier="Tier 3", regions=["RU"], free_tier=False, website="https://www.reg.ru", api_url="https://api.reg.ru", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="beget", country="Russia", tier="Tier 3", regions=["RU"], free_tier=False, website="https://beget.com", api_url="https://api.beget.com", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="timeweb", country="Russia", tier="Tier 3", regions=["RU"], free_tier=False, website="https://timeweb.cloud", api_url="https://timeweb.cloud", vpn_required=True, vpn_country="Russia"),
    CloudProvider(name="hostinger_cloud", country="Lithuania", tier="Tier 2", regions=["global"], free_tier=True, website="https://www.hostinger.com", api_url="https://developers.hostinger.com", vpn_required=False),
    CloudProvider(name="a2hosting", country="United States", tier="Tier 2", regions=["US","EU","ASIA"], free_tier=False, website="https://www.a2hosting.com", api_url="https://www.a2hosting.com", vpn_required=False),
    CloudProvider(name="bluehost", country="United States", tier="Tier 2", regions=["US"], free_tier=False, website="https://www.bluehost.com", api_url="https://www.bluehost.com", vpn_required=False),
    CloudProvider(name="siteground", country="Bulgaria", tier="Tier 2", regions=["EU","US","ASIA"], free_tier=False, website="https://www.siteground.com", api_url="https://www.siteground.com", vpn_required=False),
    CloudProvider(name="dreamhost", country="United States", tier="Tier 2", regions=["US"], free_tier=False, website="https://www.dreamhost.com", api_url="https://www.dreamhost.com", vpn_required=False),
    CloudProvider(name="liquidweb", country="United States", tier="Tier 2", regions=["US"], free_tier=False, website="https://www.liquidweb.com", api_url="https://www.liquidweb.com", vpn_required=False),
    CloudProvider(name="nexcess", country="United States", tier="Tier 2", regions=["US","EU"], free_tier=False, website="https://www.nexcess.net", api_url="https://www.nexcess.net", vpn_required=False),
    CloudProvider(name="wpengine", country="United States", tier="Tier 2", regions=["global"], free_tier=False, website="https://wpengine.com", api_url="https://wpengine.com", vpn_required=False),
    CloudProvider(name="kinsta", country="United States", tier="Tier 2", regions=["global"], free_tier=False, website="https://kinsta.com", api_url="https://kinsta.com", vpn_required=False),
    CloudProvider(name="cloudways", country="Malta", tier="Tier 2", regions=["global"], free_tier=False, website="https://www.cloudways.com", api_url="https://www.cloudways.com", vpn_required=False),
    CloudProvider(name="runcloud", country="United States", tier="Tier 2", regions=["US","EU"], free_tier=False, website="https://www.runcloud.com", api_url="https://www.runcloud.com", vpn_required=False),
    CloudProvider(name="massivesoft", country="Turkey", tier="Tier 3", regions=["TR"], free_tier=False, website="https://www.massivesoft.com.tr", api_url="", vpn_required=False),
    CloudProvider(name="turhost", country="Turkey", tier="Tier 3", regions=["TR"], free_tier=False, website="https://www.turhost.com", api_url="", vpn_required=False),
    CloudProvider(name="natro", country="Turkey", tier="Tier 3", regions=["TR"], free_tier=False, website="https://www.natro.com", api_url="", vpn_required=False),
    CloudProvider(name="sahara_net", country="Saudi Arabia", tier="Tier 3", regions=["SA"], free_tier=False, website="https://www.sahara.com.sa", api_url="", vpn_required=False),
    CloudProvider(name="mobily_cloud", country="Saudi Arabia", tier="Tier 3", regions=["SA"], free_tier=False, website="https://www.mobily.com.sa", api_url="", vpn_required=False),
    CloudProvider(name="stc_cloud", country="Saudi Arabia", tier="Tier 2", regions=["SA"], free_tier=False, website="https://www.stc.com.sa", api_url="", vpn_required=False),
    CloudProvider(name="etisalat_cloud", country="UAE", tier="Tier 2", regions=["AE"], free_tier=False, website="https://www.etisalat.ae", api_url="", vpn_required=False),
    CloudProvider(name="du_cloud", country="UAE", tier="Tier 3", regions=["AE"], free_tier=False, website="https://www.du.ae", api_url="", vpn_required=False),
    CloudProvider(name="ooredoo_cloud", country="Qatar", tier="Tier 3", regions=["QA"], free_tier=False, website="https://www.ooredoo.qa", api_url="", vpn_required=False),
    CloudProvider(name="zain_cloud", country="Kuwait", tier="Tier 3", regions=["KW"], free_tier=False, website="https://www.zain.com", api_url="", vpn_required=False),
    CloudProvider(name="orange_cloud", country="France", tier="Tier 2", regions=["FR","AF","ME"], free_tier=False, website="https://www.orange-business.com", api_url="", vpn_required=False),
    CloudProvider(name="deutsche_telekom_otc", country="Germany", tier="Tier 1", regions=["EU"], free_tier=False, website="https://open-telekom-cloud.com", api_url="https://ecs.eu-de.otc.t-systems.com", vpn_required=False),
    CloudProvider(name="ovh_us", country="United States", tier="Tier 1", regions=["US-EAST","US-WEST"], free_tier=True, website="https://us.ovhcloud.com", api_url="https://api.us.ovhcloud.com", vpn_required=False),
    CloudProvider(name="scaleway_nl", country="Netherlands", tier="Tier 1", regions=["nl-ams"], free_tier=True, website="https://www.scaleway.com", api_url="https://api.scaleway.com", vpn_required=False),
    CloudProvider(name="exoscale", country="Switzerland", tier="Tier 2", regions=["CH","DE","AT"], free_tier=True, website="https://www.exoscale.com", api_url="https://api.exoscale.com", vpn_required=False),
    CloudProvider(name="cloudsigma", country="Switzerland", tier="Tier 2", regions=["CH","US","EU","ASIA"], free_tier=False, website="https://www.cloudsigma.com", api_url="https://zrh.cloudsigma.com/api", vpn_required=False),
    CloudProvider(name="linode_akamai", country="United States", tier="Tier 1", regions=["global"], free_tier=True, website="https://www.linode.com", api_url="https://api.linode.com", vpn_required=False),
    CloudProvider(name="akamai_connected_cloud", country="United States", tier="Tier 1", regions=["global"], free_tier=False, website="https://www.akamai.com", api_url="https://api.linode.com", vpn_required=False),
    CloudProvider(name="fastly", country="United States", tier="Tier 1", regions=["global"], free_tier=True, website="https://www.fastly.com", api_url="https://api.fastly.com", vpn_required=False),
    CloudProvider(name="cloudflare_r2_workers", country="United States", tier="Tier 1", regions=["global"], free_tier=True, website="https://www.cloudflare.com", api_url="https://api.cloudflare.com", vpn_required=False),
    CloudProvider(name="backblaze_b2", country="United States", tier="Tier 1", regions=["US"], free_tier=True, website="https://www.backblaze.com", api_url="https://api.backblazeb2.com", vpn_required=False),
    CloudProvider(name="wasabi", country="United States", tier="Tier 1", regions=["US","EU","APAC"], free_tier=False, website="https://wasabi.com", api_url="https://s3.wasabisys.com", vpn_required=False),
    CloudProvider(name="digitalocean_spaces", country="United States", tier="Tier 1", regions=["global"], free_tier=True, website="https://www.digitalocean.com", api_url="https://api.digitalocean.com", vpn_required=False),
    CloudProvider(name="ibm_cloud_satellite", country="United States", tier="Tier 1", regions=["global"], free_tier=False, website="https://www.ibm.com/cloud", api_url="https://cloud.ibm.com", vpn_required=False),
    CloudProvider(name="oracle_free_tier", country="United States", tier="Tier 1", regions=["global"], free_tier=True, website="https://www.oracle.com/cloud/free", api_url="https://iaas.oraclecloud.com", vpn_required=False),
    CloudProvider(name="render", country="United States", tier="Tier 2", regions=["global"], free_tier=True, website="https://render.com", api_url="https://api.render.com", vpn_required=False),
    CloudProvider(name="railway", country="United States", tier="Tier 2", regions=["global"], free_tier=True, website="https://railway.app", api_url="https://backboard.railway.app", vpn_required=False),
    CloudProvider(name="fly_io", country="United States", tier="Tier 2", regions=["global"], free_tier=True, website="https://fly.io", api_url="https://api.fly.io", vpn_required=False),
    CloudProvider(name="vercel", country="United States", tier="Tier 2", regions=["global"], free_tier=True, website="https://vercel.com", api_url="https://api.vercel.com", vpn_required=False),
    CloudProvider(name="netlify", country="United States", tier="Tier 2", regions=["global"], free_tier=True, website="https://www.netlify.com", api_url="https://api.netlify.com", vpn_required=False),
    CloudProvider(name="heroku", country="United States", tier="Tier 2", regions=["global"], free_tier=False, website="https://www.heroku.com", api_url="https://api.heroku.com", vpn_required=False),
    CloudProvider(name="platform_sh", country="France", tier="Tier 2", regions=["EU","US"], free_tier=False, website="https://platform.sh", api_url="https://api.platform.sh", vpn_required=False),
    CloudProvider(name="clever_cloud", country="France", tier="Tier 2", regions=["EU"], free_tier=True, website="https://www.clever-cloud.com", api_url="https://api.clever-cloud.com", vpn_required=False),
    CloudProvider(name="alwaysdata", country="France", tier="Tier 3", regions=["FR"], free_tier=True, website="https://www.alwaysdata.com", api_url="https://api.alwaysdata.com", vpn_required=False),
    CloudProvider(name="gandi", country="France", tier="Tier 2", regions=["FR","LU"], free_tier=False, website="https://www.gandi.net", api_url="https://api.gandi.net", vpn_required=False),
    CloudProvider(name="online_net", country="France", tier="Tier 2", regions=["FR"], free_tier=False, website="https://www.online.net", api_url="https://api.online.net", vpn_required=False),
    CloudProvider(name="infomaniak", country="Switzerland", tier="Tier 2", regions=["CH"], free_tier=False, website="https://www.infomaniak.com", api_url="https://api.infomaniak.com", vpn_required=False),
    CloudProvider(name="hetzner_robot", country="Germany", tier="Tier 1", regions=["DE","FI"], free_tier=False, website="https://robot.hetzner.com", api_url="https://robot-ws.your-server.de", vpn_required=False),
    CloudProvider(name="leaseweb", country="Netherlands", tier="Tier 1", regions=["NL","DE","US","SG","HK","AU"], free_tier=False, website="https://www.leaseweb.com", api_url="https://api.leaseweb.com", vpn_required=False),
    CloudProvider(name="worldstream", country="Netherlands", tier="Tier 2", regions=["NL"], free_tier=False, website="https://www.worldstream.com", api_url="", vpn_required=False),
    CloudProvider(name="transip", country="Netherlands", tier="Tier 2", regions=["NL"], free_tier=False, website="https://www.transip.nl", api_url="https://api.transip.nl", vpn_required=False),
    CloudProvider(name="tilaa", country="Netherlands", tier="Tier 2", regions=["NL"], free_tier=False, website="https://www.tilaa.com", api_url="", vpn_required=False),
    CloudProvider(name="serverspace", country="Netherlands", tier="Tier 2", regions=["EU","US","ASIA"], free_tier=True, website="https://serverspace.io", api_url="https://api.serverspace.io", vpn_required=False),
    CloudProvider(name="vps_net", country="United Kingdom", tier="Tier 2", regions=["UK","US","EU"], free_tier=False, website="https://www.vps.net", api_url="", vpn_required=False),
    CloudProvider(name="fasthosts", country="United Kingdom", tier="Tier 2", regions=["UK"], free_tier=False, website="https://www.fasthosts.co.uk", api_url="", vpn_required=False),
    CloudProvider(name="ionos_uk", country="United Kingdom", tier="Tier 2", regions=["UK"], free_tier=True, website="https://www.ionos.co.uk", api_url="https://api.ionos.com", vpn_required=False),
    CloudProvider(name="aiven", country="Finland", tier="Tier 1", regions=["global"], free_tier=True, website="https://aiven.io", api_url="https://api.aiven.io", vpn_required=False),
    CloudProvider(name="upcloud_sg", country="Singapore", tier="Tier 1", regions=["sg-sin1"], free_tier=True, website="https://upcloud.com", api_url="https://api.upcloud.com", vpn_required=False),
    CloudProvider(name="vultr_tokyo", country="Japan", tier="Tier 1", regions=["nrt"], free_tier=True, website="https://www.vultr.com", api_url="https://api.vultr.com", vpn_required=False),
    CloudProvider(name="linode_tokyo", country="Japan", tier="Tier 1", regions=["ap-northeast"], free_tier=True, website="https://www.linode.com", api_url="https://api.linode.com", vpn_required=False),
    CloudProvider(name="sakura_cloud", country="Japan", tier="Tier 2", regions=["JP"], free_tier=True, website="https://cloud.sakura.ad.jp", api_url="https://secure.sakura.ad.jp/cloud", vpn_required=False),
    CloudProvider(name="idcf_cloud", country="Japan", tier="Tier 2", regions=["JP"], free_tier=False, website="https://www.idcf.jp/cloud", api_url="", vpn_required=False),
    CloudProvider(name="conoha", country="Japan", tier="Tier 2", regions=["JP"], free_tier=True, website="https://www.conoha.jp", api_url="", vpn_required=False),
    CloudProvider(name="naver_cloud_platform", country="South Korea", tier="Tier 2", regions=["KR"], free_tier=True, website="https://www.ncloud.com", api_url="https://ncloud.com", vpn_required=True, vpn_country="South Korea"),
    CloudProvider(name="kakao_i_cloud", country="South Korea", tier="Tier 2", regions=["KR"], free_tier=False, website="https://kakaocloud.com", api_url="", vpn_required=True, vpn_country="South Korea"),
    CloudProvider(name="kt_cloud", country="South Korea", tier="Tier 2", regions=["KR"], free_tier=False, website="https://cloud.kt.com", api_url="", vpn_required=True, vpn_country="South Korea"),
    CloudProvider(name="nhn_cloud", country="South Korea", tier="Tier 2", regions=["KR"], free_tier=False, website="https://www.nhncloud.com", api_url="", vpn_required=True, vpn_country="South Korea"),
    CloudProvider(name="alibaba_in", country="India", tier="Tier 1", regions=["ap-south-1"], free_tier=True, website="https://www.alibabacloud.com", api_url="https://ecs.aliyuncs.com", vpn_required=False),
    CloudProvider(name="aws_mumbai", country="India", tier="Tier 1", regions=["ap-south-1"], free_tier=True, website="https://aws.amazon.com", api_url="https://ec2.amazonaws.com", vpn_required=False),
    CloudProvider(name="azure_india", country="India", tier="Tier 1", regions=["centralindia","southindia"], free_tier=True, website="https://azure.microsoft.com", api_url="https://management.azure.com", vpn_required=False),
    CloudProvider(name="gcp_india", country="India", tier="Tier 1", regions=["asia-south1","asia-south2"], free_tier=True, website="https://cloud.google.com", api_url="https://cloud.googleapis.com", vpn_required=False),
    CloudProvider(name="jio_cloud", country="India", tier="Tier 2", regions=["IN"], free_tier=True, website="https://cloud.jio.com", api_url="", vpn_required=False),
    CloudProvider(name="tata_comms_cloud", country="India", tier="Tier 2", regions=["IN"], free_tier=False, website="https://www.tatacommunications.com", api_url="", vpn_required=False),
    CloudProvider(name="ctrl_s", country="India", tier="Tier 3", regions=["IN"], free_tier=False, website="https://www.ctrls.in", api_url="", vpn_required=False),
    CloudProvider(name="e2e_networks", country="India", tier="Tier 3", regions=["IN"], free_tier=False, website="https://www.e2enetworks.com", api_url="", vpn_required=False),
    CloudProvider(name="digitalocean_blr", country="India", tier="Tier 1", regions=["blr1"], free_tier=True, website="https://www.digitalocean.com", api_url="https://api.digitalocean.com", vpn_required=False),
    CloudProvider(name="linode_mumbai", country="India", tier="Tier 1", regions=["ap-west"], free_tier=True, website="https://www.linode.com", api_url="https://api.linode.com", vpn_required=False),
    CloudProvider(name="vultr_bangalore", country="India", tier="Tier 1", regions=["blr"], free_tier=True, website="https://www.vultr.com", api_url="https://api.vultr.com", vpn_required=False),
    CloudProvider(name="aws_sydney", country="Australia", tier="Tier 1", regions=["ap-southeast-2"], free_tier=True, website="https://aws.amazon.com", api_url="https://ec2.amazonaws.com", vpn_required=False),
    CloudProvider(name="azure_australia", country="Australia", tier="Tier 1", regions=["australiaeast","australiasoutheast"], free_tier=True, website="https://azure.microsoft.com", api_url="https://management.azure.com", vpn_required=False),
    CloudProvider(name="gcp_sydney", country="Australia", tier="Tier 1", regions=["australia-southeast1"], free_tier=True, website="https://cloud.google.com", api_url="https://cloud.googleapis.com", vpn_required=False),
    CloudProvider(name="binarylane", country="Australia", tier="Tier 2", regions=["AU"], free_tier=False, website="https://www.binarylane.com.au", api_url="", vpn_required=False),
    CloudProvider(name="vultr_sydney", country="Australia", tier="Tier 1", regions=["syd"], free_tier=True, website="https://www.vultr.com", api_url="https://api.vultr.com", vpn_required=False),
    CloudProvider(name="linode_sydney", country="Australia", tier="Tier 1", regions=["ap-southeast"], free_tier=True, website="https://www.linode.com", api_url="https://api.linode.com", vpn_required=False),
    CloudProvider(name="aws_saopaulo", country="Brazil", tier="Tier 1", regions=["sa-east-1"], free_tier=True, website="https://aws.amazon.com", api_url="https://ec2.amazonaws.com", vpn_required=False),
    CloudProvider(name="azure_brazil", country="Brazil", tier="Tier 1", regions=["brazilsouth"], free_tier=True, website="https://azure.microsoft.com", api_url="https://management.azure.com", vpn_required=False),
    CloudProvider(name="gcp_saopaulo", country="Brazil", tier="Tier 1", regions=["southamerica-east1"], free_tier=True, website="https://cloud.google.com", api_url="https://cloud.googleapis.com", vpn_required=False),
    CloudProvider(name="locaweb", country="Brazil", tier="Tier 3", regions=["BR"], free_tier=False, website="https://www.locaweb.com.br", api_url="", vpn_required=False),
    CloudProvider(name="kinghost", country="Brazil", tier="Tier 3", regions=["BR"], free_tier=False, website="https://king.host", api_url="", vpn_required=False),
    CloudProvider(name="aws_cape_town", country="South Africa", tier="Tier 1", regions=["af-south-1"], free_tier=True, website="https://aws.amazon.com", api_url="https://ec2.amazonaws.com", vpn_required=False),
    CloudProvider(name="azure_africa", country="South Africa", tier="Tier 1", regions=["southafricanorth"], free_tier=True, website="https://azure.microsoft.com", api_url="https://management.azure.com", vpn_required=False),
    CloudProvider(name="gcp_johannesburg", country="South Africa", tier="Tier 1", regions=["africa-south1"], free_tier=True, website="https://cloud.google.com", api_url="https://cloud.googleapis.com", vpn_required=False),
    CloudProvider(name="xneelo", country="South Africa", tier="Tier 3", regions=["ZA"], free_tier=False, website="https://xneelo.com", api_url="", vpn_required=False),
    CloudProvider(name="afrihost", country="South Africa", tier="Tier 3", regions=["ZA"], free_tier=False, website="https://www.afrihost.com", api_url="", vpn_required=False),
]


ALL_PROVIDERS = TIER_1_PROVIDERS + TIER_2_PROVIDERS + TIER_3_NORTH_AMERICA + TIER_3_SOUTH_AMERICA + TIER_3_EUROPE + TIER_3_ASIA + TIER_3_AFRICA + TIER_3_MIDDLE_EAST + TIER_3_OCEANIA + EXTRA_CLOUD_PROVIDERS


def get_providers_by_country(country: str) -> List[CloudProvider]:
    """الحصول على جميع المزودين في دولة معينة"""
    return [p for p in ALL_PROVIDERS if p.country == country]


def get_providers_by_tier(tier: str) -> List[CloudProvider]:
    """الحصول على جميع المزودين حسب Tier"""
    return [p for p in ALL_PROVIDERS if p.tier == tier]


def get_providers_require_vpn() -> List[CloudProvider]:
    """الحصول على جميع المزودين الذين يتطلبون VPN"""
    return [p for p in ALL_PROVIDERS if p.vpn_required]


def get_providers_with_free_tier() -> List[CloudProvider]:
    """الحصول على جميع المزودين الذين يقدمون خطة مجانية"""
    return [p for p in ALL_PROVIDERS if p.free_tier]


def get_providers_by_region(region: str) -> List[CloudProvider]:
    """الحصول على جميع المزودين الذين يدعمون منطقة معينة"""
    return [p for p in ALL_PROVIDERS if region in p.regions]


def get_vpn_required_countries() -> List[str]:
    """الحصول على قائمة جميع الدول التي تتطلب VPN"""
    countries = set()
    for provider in ALL_PROVIDERS:
        if provider.vpn_required and provider.vpn_country:
            countries.add(provider.vpn_country)
    return sorted(list(countries))


def get_provider_by_name(name: str) -> Optional[CloudProvider]:
    """الحصول على مزود معين حسب الاسم"""
    for provider in ALL_PROVIDERS:
        if provider.name == name:
            return provider
    return None


# ============================================================================
# إحصائيات
# ============================================================================

STATS = {
    "total_providers": len(ALL_PROVIDERS),
    "tier_1_count": len([p for p in ALL_PROVIDERS if p.tier == "Tier 1"]),
    "tier_2_count": len([p for p in ALL_PROVIDERS if p.tier == "Tier 2"]),
    "tier_3_count": len([p for p in ALL_PROVIDERS if p.tier == "Tier 3"]),
    "free_tier_count": len(get_providers_with_free_tier()),
    "vpn_required_count": len(get_providers_require_vpn()),
    "countries_count": len(set(p.country for p in ALL_PROVIDERS)),
    "vpn_countries_count": len(get_vpn_required_countries()),
}


if __name__ == "__main__":
    print("=" * 80)
    print("CLOUD PROVIDERS DATABASE")
    print("=" * 80)
    print(f"\n📊 إحصائيات:")
    print(f"  - إجمالي المزودين: {STATS['total_providers']}")
    print(f"  - Tier 1 (عالمي): {STATS['tier_1_count']}")
    print(f"  - Tier 2 (إقليمي): {STATS['tier_2_count']}")
    print(f"  - Tier 3 (محلي): {STATS['tier_3_count']}")
    print(f"  - مزودون مجانيون: {STATS['free_tier_count']}")
    print(f"  - مزودون يتطلبون VPN: {STATS['vpn_required_count']}")
    print(f"  - دول مزودي السحابة: {STATS['countries_count']}")
    print(f"  - دول تتطلب VPN: {STATS['vpn_countries_count']}")
    
    print(f"\n🌍 دول تتطلب VPN ({STATS['vpn_countries_count']} دولة):")
    vpn_countries = get_vpn_required_countries()
    for i, country in enumerate(vpn_countries, 1):
        providers = get_providers_by_country(country)
        print(f"  {i}. {country}: {len(providers)} مزود")
    
    print(f"\n🎁 مزودون مجانيون ({STATS['free_tier_count']} مزود):")
    for i, provider in enumerate(get_providers_with_free_tier(), 1):
        print(f"  {i}. {provider.name} ({provider.country})")
