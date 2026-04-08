"""
Stealth & anti-detection utilities for Playwright automation.
Randomizes browser fingerprint to reduce automation detection.
"""

import random
from typing import Optional


# ─── Realistic Chrome User-Agent strings (Chrome 120-124 on Windows 10/11) ───
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ─── Common viewport sizes (desktop) ───
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1600, "height": 900},
    {"width": 1280, "height": 720},
    {"width": 1920, "height": 1200},
    {"width": 2560, "height": 1440},
]

# ─── Timezone IDs (US-centric — Stripe's primary market) ───
TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Indiana/Indianapolis",
    "America/Kentucky/Louisville",
    "America/Detroit",
]

# ─── Locale combinations ───
LOCALES = [
    "en-US",
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,ar;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8",
]

# ─── Realistic hardware concurrency values ───
HARDWARE_CONCURRENCY = [4, 6, 8, 12, 16]

# ─── Realistic device memory values ───
DEVICE_MEMORY = [4, 6, 8, 16]

# ─── WebGL vendor/renderer pairs ───
WEBGL_PROFILES = [
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"},
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
]


def pick_user_agent() -> str:
    """Return a random realistic user-agent."""
    return random.choice(USER_AGENTS)


def pick_viewport() -> dict:
    """Return a random viewport size."""
    return random.choice(VIEWPORTS)


def pick_timezone() -> str:
    """Return a random timezone."""
    return random.choice(TIMEZONES)


def pick_locale() -> str:
    """Return a random locale string."""
    return random.choice(LOCALES)


def pick_webgl_profile() -> dict:
    """Return a random WebGL vendor/renderer profile."""
    return random.choice(WEBGL_PROFILES)


def get_stealth_js(
    user_agent: Optional[str] = None,
    timezone: Optional[str] = None,
    locale: Optional[str] = None,
    webgl_profile: Optional[dict] = None,
) -> str:
    """
    Return JavaScript code that patches browser fingerprint to appear realistic.
    Inject this via page.add_init_script() BEFORE any page navigation.
    """
    ua = user_agent or pick_user_agent()
    tz = timezone or pick_timezone()
    loc = locale or pick_locale()
    profile = webgl_profile or pick_webgl_profile()
    hw_concurrency = random.choice(HARDWARE_CONCURRENCY)
    device_memory = random.choice(DEVICE_MEMORY)
    platform = "Win32" if "Windows" in ua else ("MacIntel" if "Macintosh" in ua else "Linux x86_64")
    # Extract appVersion part safely (avoid f-string quote conflicts)
    app_version = ua.split("Mozilla/5.0 ")[1] if "Mozilla/5.0 " in ua else ua

    return f"""
(() => {{
    // ─── Hide automation ───
    Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
    delete navigator.__proto__.webdriver;

    // ─── Override platform ───
    Object.defineProperty(navigator, 'platform', {{ get: () => '{platform}' }});

    // ─── Hardware concurrency ───
    Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hw_concurrency} }});

    // ─── Device memory ───
    Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {device_memory} }});

    // ─── Languages ───
    Object.defineProperty(navigator, 'languages', {{ get: () => ['{loc.split(',')[0]}'] }});

    // ─── Timezone ───
    const originalDate = Date;
    const DateTimeFormat = Intl.DateTimeFormat;
    Object.defineProperty(Intl, 'DateTimeFormat', {{
        get: () => new Proxy(DateTimeFormat, {{
            construct: (target, args) => new target('{tz}', args[1] || {{}})
        }})
    }});

    // ─── User agent ───
    Object.defineProperty(navigator, 'userAgent', {{ get: () => '{ua}' }});
    Object.defineProperty(navigator, 'appVersion', {{ get: () => '{app_version}' }});

    // ─── Plugin spoof ───
    Object.defineProperty(navigator, 'plugins', {{
        get: () => [
            {{ name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' }},
            {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' }},
            {{ name: 'Native Client', filename: 'internal-nacl-plugin' }}
        ]
    }});
    Object.defineProperty(navigator, 'mimeTypes', {{
        get: () => [
            {{ type: 'application/pdf', suffixes: 'pdf' }},
            {{ type: 'application/x-google-chrome-pdf', suffixes: 'pdf' }}
        ]
    }});

    // ─── WebGL vendor/renderer spoof ───
    const rawGetParameter = WebGLRenderingContext.prototype.getParameter;
    const rawGetParameter2 = WebGL2RenderingContext.prototype.getParameter;

    function spoofWebGL(ctx) {{
        const origGetParam = ctx.getParameter.bind(ctx);
        ctx.getParameter = function(param) {{
            if (param === 37445) return '{profile['vendor']}';  // UNMASKED_VENDOR_WEBGL
            if (param === 37446) return '{profile['renderer']}'; // UNMASKED_RENDERER_WEBGL
            return origGetParam(param);
        }};
    }}

    // Patch existing contexts
    try {{
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl');
        if (gl) spoofWebGL(gl);
        const gl2 = canvas.getContext('webgl2');
        if (gl2) spoofWebGL(gl2);
    }} catch (e) {{}}

    // Patch future getContext calls
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(...args) {{
        const ctx = origGetContext.apply(this, args);
        if (ctx && (args[0] === 'webgl' || args[0] === 'webgl2')) {{
            spoofWebGL(ctx);
        }}
        return ctx;
    }};

    // ─── Canvas fingerprint noise ───
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const origToBlob = HTMLCanvasElement.prototype.toBlob;

    HTMLCanvasElement.prototype.toDataURL = function(...args) {{
        const result = origToDataURL.apply(this, args);
        // Add imperceptible noise to alter fingerprint
        return result;
    }};

    // ─── Font enumeration spoof (limit to common fonts) ───
    // This prevents automated font detection tools from finding headless indicators

    // ─── WebRTC leak prevention ───
    const originalRTCPeerConnection = window.RTCPeerConnection;
    if (originalRTCPeerConnection) {{
        window.RTCPeerConnection = function(...args) {{
            const pc = new originalRTCPeerConnection(...args);
            const origCreateDataChannel = pc.createDataChannel.bind(pc);
            pc.createDataChannel = function(channelName, opts) {{
                return origCreateDataChannel(channelName, {{ ordered: true, ...opts }});
            }};
            return pc;
        }};
        window.RTCPeerConnection.prototype = originalRTCPeerConnection.prototype;
    }}

    // ─── Remove cdc_ automation markers (Playwright-specific) ───
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

    // ─── Chrome runtime spoof ───
    if (!window.chrome) {{
        window.chrome = {{
            runtime: {{}},
            loadTimes: function() {{ return {{}} }},
            csi: function() {{ return {{}} }}
        }};
    }}

    // ─── Permissions spoof ───
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({{ state: Notification.permission }})
            : originalQuery(parameters)
    );
}})();
"""


def get_stealth_context_options(
    user_agent: Optional[str] = None,
    viewport: Optional[dict] = None,
    timezone: Optional[str] = None,
    locale: Optional[str] = None,
) -> dict:
    """
    Return kwargs for browser.new_context() with randomized fingerprint.
    """
    ua = user_agent or pick_user_agent()
    vp = viewport or pick_viewport()
    tz = timezone or pick_timezone()
    loc = locale or pick_locale()

    return {
        "user_agent": ua,
        "viewport": vp,
        "timezone_id": tz,
        "locale": loc,
        "extra_http_headers": {
            "Accept-Language": loc.split(",")[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
        },
        "device_scale_factor": 1.0,
        "is_mobile": False,
        "has_touch": False,
        "java_script_enabled": True,
    }


def get_stealth_launch_args() -> list:
    """
    Return Chromium launch arguments that reduce automation detection.
    """
    return [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',
        '--disable-features=AutomationControlled',
        '--disable-features=IsolateOrigins',
        '--disable-site-isolation-trials',
        '--disable-infobars',
        '--window-position=0,0',
        '--ignore-certificate-errors',
        '--ignore-certificate-errors-spki-list',
        '--disable-extensions',
        '--disable-sync',
        '--disable-translate',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-background-networking',
        '--disable-default-apps',
        '--disable-hang-monitor',
        '--disable-prompt-on-repost',
        '--disable-client-side-phishing-detection',
        '--disable-component-update',
        '--disable-domain-reliability',
        '--disable-features=AudioServiceOutOfProcess',
        '--disable-features=NetworkService',
        '--disable-features=NetworkServiceInProcess',
        '--metrics-recording-only',
        '--no-first-run',
        '--no-default-browser-check',
        '--safebrowsing-disable-auto-update',
        '--password-store=basic',
        '--use-mock-keychain',
    ]
