import gradio as gr
from app import config, i18n, voice_library, presets, tts_engine

# ── 视觉设计：青瓷暖声 (celadon · warm voice) ─────────────────────────────
# PC 桌面工具：宽幅双栏布局；品牌色 = 青瓷玉绿(信任/沉静/本地私密)，
# 标志 = 「」说话引号(把文字"说出来")。整页暖中性，胆量只花在玉绿一处。
HEAD = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Noto+Sans+SC:wght@400;500;700&'
    'family=Noto+Serif+SC:wght@400;700;900&'
    'family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">'
    # (1) Force light theme (deliberately light celadon design; dark mode breaks it).
    # (2) Manual UI language: persist ?__lang= to localStorage and keep it in the URL
    #     (so the server-side relabel sees it); reflect on <html data-uilang> for the
    #     switcher's active state. The actual relabel happens server-side on demo.load.
    '<script>(function(){try{'
    'var u=new URL(window.location.href),p=u.searchParams,changed=false;'
    "var lang=p.get('__lang')||localStorage.getItem('ev_uilang')||'';"
    "if(p.get('__theme')!=='light'){p.set('__theme','light');changed=true;}"
    "if(lang&&p.get('__lang')!==lang){p.set('__lang',lang);changed=true;}"
    "if(lang){localStorage.setItem('ev_uilang',lang);}"
    'if(changed){window.location.replace(u.href);return;}'
    # theme is light & already applied by Gradio on load → drop the ugly ?__theme= from the address bar
    "if(p.has('__theme')){p.delete('__theme');history.replaceState(null,'',u.pathname+(p.toString()?'?'+p.toString():'')+u.hash);}"
    "document.documentElement.setAttribute('data-uilang',lang||'auto');"
    '}catch(e){}})();</script>'
)

THEME = gr.themes.Soft()

# 浏览器标签页图标（声·青瓷 mark）；随 app/ 一起打进整合包
FAVICON = str(config.ROOT / "app" / "assets" / "brand" / "favicon.png")

CSS = """
:root{
  --ink:#1E2A23; --jade:#1C9C77; --jade-d:#127155; --mint:#8FE0C2;
  --paper:#EAF0E7; --surface:#FFFFFF; --sand:#F4EEE1;
  --line:#D7E2D5; --muted:#54625A; --r:16px;
}

/* retheme Gradio via its own CSS variables (robust, not selector hacks) */
.gradio-container{
  --body-background-fill:var(--paper);
  --background-fill-primary:var(--surface);
  --background-fill-secondary:var(--sand);
  --block-background-fill:var(--surface);
  --block-border-color:var(--line);
  --block-border-width:0px;
  --block-shadow:none;
  --block-label-background-fill:transparent;
  --block-label-text-color:var(--ink);
  --block-title-text-color:var(--ink);
  --block-info-text-color:var(--muted);
  --border-color-primary:var(--line);
  --border-color-accent:var(--jade);
  --input-background-fill:#FFFFFF;
  --input-border-color:var(--line);
  --input-border-color-focus:var(--jade);
  --input-radius:11px;
  --button-large-radius:12px;
  --button-small-radius:10px;
  --button-primary-background-fill:var(--jade);
  --button-primary-background-fill-hover:var(--jade-d);
  --button-primary-text-color:#FFFFFF;
  --button-primary-border-color:var(--jade);
  --button-secondary-background-fill:#FFFFFF;
  --button-secondary-background-fill-hover:#F1F5EF;
  --button-secondary-border-color:var(--line);
  --button-secondary-text-color:var(--ink);
  --color-accent:var(--jade);
  --color-accent-soft:rgba(28,156,119,.12);
  --slider-color:var(--jade);
  --checkbox-label-background-fill-selected:rgba(28,156,119,.14);
  --checkbox-label-border-color-selected:var(--jade);
  --checkbox-background-color-selected:var(--jade);
  --checkbox-border-color-selected:var(--jade);
}

.gradio-container{ background:var(--paper)!important; width:100%!important; max-width:1200px!important;
  margin:0 auto!important; padding:0 20px 48px!important; align-items:stretch!important;
  font-family:'Noto Sans SC',system-ui,sans-serif; color:var(--ink); font-size:15px;}
.gradio-container *{ font-family:'Noto Sans SC',system-ui,sans-serif; }
footer{ display:none!important; }

/* Every tab fills the SAME width — Gradio otherwise shrink-wraps main to its
   content, so tabs with more/wider content (e.g. the preset readout) render wider. */
.gradio-container main.contain{ width:100%!important; max-width:100%!important;}
.gradio-container .tabs, .gradio-container .tabitem,
.gradio-container main.contain > .column,
.gradio-container .tabitem > .column{ width:100%!important;}
/* Flatten Gradio's grouped-input sub-boxes (the sage "box-in-box" layers) */
.gradio-container .styler{ background:transparent!important;}
.gradio-container .form{ background:transparent!important; border:none!important; gap:14px!important;}

/* global sage background everywhere (outside the container too) + light controls */
:root{ color-scheme:light; }
html, body, gradio-app{ background:var(--paper)!important; }
/* defensive: if OS dark mode ever slips past the force-light redirect, keep it light */
.dark{ --body-background-fill:var(--paper); --background-fill-primary:var(--surface);
  --background-fill-secondary:var(--sand); --block-background-fill:var(--surface);
  --input-background-fill:#FFFFFF; --border-color-primary:var(--line);
  --block-border-color:var(--line); --body-text-color:var(--ink);
  --block-label-text-color:var(--ink); --block-info-text-color:var(--muted);}
.dark .ev-card, .dark .ev-step, .dark .gradio-container{ background:var(--paper);}

/* safe: any stray container-block border -> sage (0-width input blocks unaffected) */
.gradio-container .block{ border-color:var(--line)!important; }
.gradio-container .block:has(> .ev-hero),
.gradio-container .block:has(> .ev-steps),
.gradio-container .block:has(> .ev-eyebrow){ border:none!important; background:transparent!important;
  padding:0!important; box-shadow:none!important;}

/* ── hero band ─────────────────────────────────────────── */
.ev-hero{ position:relative; overflow:hidden; border-radius:20px; margin:16px 0 6px;
  padding:30px 40px 34px; color:#EAF4EE;
  background:linear-gradient(125deg,#0E5341 0%,#16745A 55%,#1C9270 100%);
  box-shadow:0 18px 44px -20px rgba(14,83,65,.6); animation:evfade .6s ease both;}
@keyframes evfade{ from{opacity:0; transform:translateY(6px);} to{opacity:1; transform:none;} }
.ev-mark{ position:absolute; right:22px; bottom:-92px; font-family:'Noto Serif SC',serif;
  font-weight:900; font-size:300px; line-height:1; color:#D9F2E6; opacity:.07;
  pointer-events:none; user-select:none;}
.ev-hero-row{ position:relative; z-index:1; display:flex; align-items:center;
  justify-content:space-between; gap:14px; flex-wrap:wrap;}
.ev-brand{ display:flex; align-items:baseline; gap:12px;}
.ev-logo{ font-family:'Noto Serif SC',serif; font-weight:900; font-size:32px; letter-spacing:3px; color:#fff;}
.ev-en{ font-family:'Space Mono',monospace; font-size:12px; letter-spacing:5px; color:#C8EAD8;}
.ev-status{ display:inline-flex; align-items:center; gap:8px; white-space:nowrap;
  font-size:13px; color:#F0F8F3; background:rgba(255,255,255,.14); padding:7px 14px; border-radius:999px;}
.ev-hero-right{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end;}
.ev-lang{ display:inline-flex; gap:2px; background:rgba(255,255,255,.18);
  border:1px solid rgba(255,255,255,.30); border-radius:999px; padding:3px;}
.ev-lang a{ color:#EAF7F0; font-size:13px; font-weight:600; line-height:1; padding:5px 11px; border-radius:999px;
  text-decoration:none; cursor:pointer; transition:color .12s, background .12s;}
.ev-lang a:hover{ color:#fff; background:rgba(255,255,255,.16);}
html[data-uilang="zh"] .ev-lang .lang-zh,
html[data-uilang="zh-Hant"] .ev-lang .lang-zhhant,
html[data-uilang="en"] .ev-lang .lang-en{ background:#fff; color:var(--jade-d); font-weight:700;}
.ev-dot{ width:8px; height:8px; border-radius:50%;}
.ev-dot.live{ background:#8AF0C4;}
.ev-dot.idle{ background:#FFC56B;}
@media (prefers-reduced-motion:no-preference){
  .ev-dot.live{ animation:evpulse 2.6s ease-in-out infinite;}
  @keyframes evpulse{ 0%,100%{ box-shadow:0 0 0 0 rgba(138,240,196,.55);}
    50%{ box-shadow:0 0 0 5px rgba(138,240,196,0);} }
}
.ev-promise{ position:relative; z-index:1; font-family:'Noto Serif SC',serif; font-weight:700;
  font-size:46px; line-height:1.2; margin:22px 0 10px; color:#fff; letter-spacing:1px;}
.ev-qk{ color:var(--mint); font-weight:700;}
.ev-trust{ position:relative; z-index:1; margin:0; font-size:15px; color:#E7F6EE; letter-spacing:.5px;}

/* ── 3-step strip (honest sequence: pick → write → generate) ─ */
.ev-steps{ display:flex; gap:12px; margin:18px 0 4px;}
.ev-step{ flex:1; background:var(--surface); border:1px solid var(--line); border-radius:14px;
  padding:15px 18px; display:flex; gap:13px; align-items:center;}
.ev-step .n{ flex:none; width:30px; height:30px; border-radius:50%; background:rgba(28,156,119,.13);
  color:var(--jade-d); font-weight:700; font-size:15px; font-family:'Space Mono',monospace;
  display:flex; align-items:center; justify-content:center;}
.ev-step .t{ font-weight:600; color:var(--ink); font-size:15.5px; line-height:1.3;}
.ev-step .s{ color:var(--muted); font-size:13px; line-height:1.35; margin-top:2px;}

/* ── segmented tabs (equal, centered, full-width panels) ─── */
.tab-nav, .tabs>.tab-nav, [role="tablist"]{ justify-content:center!important; border:none!important;
  gap:5px!important; background:#E1E8DD!important; padding:5px!important; border-radius:999px!important;
  width:fit-content!important; margin:20px auto 14px!important;}
.tab-nav button, [role="tab"]{ border:none!important; background:transparent!important;
  border-radius:999px!important; padding:10px 26px!important; color:var(--muted)!important;
  font-weight:600!important; font-size:15px!important; transition:color .15s;}
.tab-nav button.selected, [role="tab"][aria-selected="true"]{ background:#fff!important;
  color:var(--jade-d)!important; box-shadow:0 2px 8px rgba(18,113,85,.18)!important;}
.tabitem{ padding:0!important;}

/* ── two-column row ────────────────────────────────────── */
.ev-row{ gap:18px!important; align-items:flex-start!important;}

/* ── cards ─────────────────────────────────────────────── */
/* Card box on the OUTERMOST .ev-card only. Gradio copies elem_classes onto a nested
   element too, and its .gr-group draws its own border/shadow → box-in-box. The :not()
   styles only the outer; the reset below flattens every inner wrapper. */
.gradio-container .ev-card:not(.ev-card .ev-card){ background:var(--surface)!important;
  border:1px solid var(--line)!important; border-radius:var(--r)!important; padding:22px 24px!important;
  box-shadow:0 8px 26px -18px rgba(30,42,35,.42)!important;}
.gradio-container .ev-card .ev-card,
.gradio-container .ev-card .gr-group,
.gradio-container .ev-guide .ev-guide,
.gradio-container .ev-readout .ev-readout,
.gradio-container .ev-audio .ev-audio,
.gradio-container .ev-acc .ev-acc{ border:0!important; border-radius:0!important;
  box-shadow:none!important; background:transparent!important; padding:0!important;}

/* ── section eyebrow ───────────────────────────────────── */
.ev-eyebrow{ display:flex; align-items:center; gap:9px; font-weight:700; font-size:15px;
  color:var(--ink); margin:0 0 14px;}
.ev-eyebrow::before{ content:""; width:4px; height:17px; border-radius:3px; background:var(--jade);}

/* ── guidance callout ──────────────────────────────────── */
.gradio-container .ev-guide{ color:var(--muted)!important; font-size:14px!important; line-height:1.7!important;
  background:var(--sand)!important; border:1px solid #ECE2CC!important; border-left:3px solid var(--jade)!important;
  border-radius:12px!important; padding:12px 17px!important; margin:4px 0 14px!important;}
.gradio-container .ev-guide strong{ color:var(--ink)!important;}

/* ── status line (borderless → empty leaves no visible box) ─ */
.ev-statusline{ color:var(--jade-d)!important; font-size:13.5px!important; font-weight:600!important;
  text-align:center;}
.ev-statusline, .ev-statusline *{ margin:0!important;}

/* ── advanced accordion intro hint (muted, sets "you can skip this") ─ */
.gradio-container .ev-acc-hint{ color:var(--muted)!important; font-size:13px!important;
  line-height:1.6!important; margin:-2px 0 12px!important;}
.gradio-container .ev-acc-hint *{ margin:0!important;}

/* ── voice library: per-row inline manage (name + ↑ ↓ 🗑, delete confirm) ── */
.gradio-container .ev-vrow{ align-items:center!important; gap:6px!important;
  flex-wrap:nowrap!important; margin-bottom:7px!important;}
.gradio-container .ev-vrow button{ min-width:44px!important; padding:8px 6px!important;}
/* editable inline fields (name / 参考文字稿) — Gradio renders Textbox as <textarea> */
.gradio-container .ev-edit textarea, .gradio-container .ev-edit input{ background:#fff!important;
  border:1px solid var(--line)!important; border-radius:9px!important; padding:7px 10px!important;}
.gradio-container .ev-edit textarea:focus, .gradio-container .ev-edit input:focus{
  border-color:var(--jade)!important; box-shadow:0 0 0 2px rgba(28,156,119,.12)!important;}
/* display-mode row: name as plain text grows, action buttons stay compact on the right */
.gradio-container .ev-vname{ flex:1!important; min-width:0!important;}
.gradio-container .ev-vname p{ margin:0!important; font-weight:600!important; color:var(--ink)!important;}
/* edit-mode panel (✎ 编辑 展开) */
.gradio-container .ev-editbox{ border:1px solid var(--jade)!important; border-radius:12px!important;
  background:var(--sand)!important; padding:12px!important; margin-bottom:10px!important;}
.gradio-container .ev-editbox .ev-editbtns{ gap:8px!important; margin-top:8px!important;}
.gradio-container .ev-vrow-del{ background:#FBECEA!important;
  border:1px solid #F0C9C0!important; border-radius:10px!important; padding:6px 8px!important;}
.gradio-container .ev-vrow-del p{ margin:0!important; color:var(--ink)!important; font-size:14px!important;}

/* ── 配音 preset quick bar (apply / save) + manager per-row summary ── */
.gradio-container .ev-presetbar{ align-items:flex-end!important; gap:6px!important;
  flex-wrap:nowrap!important; margin-bottom:6px!important;}
.gradio-container .ev-presetbar button{ min-width:72px!important;}
.gradio-container .ev-savebar{ margin-top:4px!important;}
.gradio-container .ev-prow-sum{ margin:-3px 0 12px 2px!important; font-size:12px!important;
  opacity:.85;}
.gradio-container .ev-prow-sum *{ margin:0!important;}
/* 最大生成长度 → 预计语音时长(随滑块实时) */
.gradio-container .ev-tokest{ margin:-6px 0 8px!important; font-size:12px!important;
  color:var(--jade-d)!important; text-align:right!important;}
.gradio-container .ev-tokest *{ margin:0!important;}

/* ── inputs ────────────────────────────────────────────── */
.gradio-container input[type=text], .gradio-container textarea{ font-size:15px!important;}
/* kill Soft-theme lavender label pill (Gradio tags the title span block-info) */
.gradio-container span[data-testid="block-info"]{ background:transparent!important;
  padding-left:0!important; padding-right:0!important;}

/* ── accordion (targeted by structure + elem_class) ────── */
.gradio-container .block:has(> .label-wrap),
.gradio-container .ev-acc{ border:1px solid var(--line)!important; border-radius:12px!important;
  background:var(--sand)!important; box-shadow:none!important; overflow:hidden;}
.gradio-container .block:has(> .label-wrap) .label-wrap,
.gradio-container .ev-acc .label-wrap{ font-weight:600!important; color:var(--jade-d)!important;}

/* ── audio (targeted by elem_class) ────────────────────── */
.gradio-container .ev-audio,
.gradio-container .block:has(.ev-audio){ border:1px solid var(--line)!important;
  border-radius:12px!important; background:#fff!important;}

/* ── style radio → 3 equal jade chips on one line (kill indigo selected) ── */
.gradio-container .ev-style{ width:100%!important;}
.gradio-container .form:has(> .ev-style){ width:100%!important; display:block!important;}
.gradio-container .ev-style .wrap{ display:flex!important; flex-wrap:nowrap!important;
  gap:8px!important; width:100%!important;}
.gradio-container .ev-style input[type=radio]{ display:none!important;}
.gradio-container .ev-style label{ flex:1 1 0!important; justify-content:center!important; min-width:0!important;
  white-space:nowrap!important; padding:9px 8px!important;
  border-radius:10px!important; border:1px solid var(--line)!important; background:#fff!important;}
.gradio-container label.selected{ background:rgba(28,156,119,.14)!important; border-color:var(--jade)!important;}
.gradio-container label.selected span{ color:var(--jade-d)!important; font-weight:600!important;}

/* ── primary generate ──────────────────────────────────── */
#ev-generate{ background:var(--jade)!important; border:none!important; color:#fff!important;
  font-size:18px!important; font-weight:700!important; letter-spacing:6px!important;
  padding:15px!important; border-radius:13px!important; margin:12px 0!important;
  box-shadow:0 14px 30px -10px rgba(28,156,119,.6)!important; transition:filter .15s, transform .12s;}
#ev-generate:hover{ filter:brightness(1.05); transform:translateY(-1px);}
#ev-generate:active{ transform:translateY(0);}

/* ── secondary buttons ─────────────────────────────────── */
.ev-card button:not(.primary){ border-radius:11px!important; font-weight:600!important;}

/* ── readout summary ───────────────────────────────────── */
.gradio-container .ev-readout{ font-family:'Space Mono','Noto Sans SC',monospace!important;
  background:var(--sand)!important; border:1px solid #ECE2CC!important; border-radius:12px!important;
  padding:13px 16px!important; color:var(--ink)!important; font-size:13.5px!important; line-height:1.7;
  white-space:normal!important; word-break:break-word; overflow-wrap:anywhere;}

/* ── focus a11y ────────────────────────────────────────── */
.gradio-container *:focus-visible{ outline:2px solid var(--jade)!important; outline-offset:2px;}

/* ── footer: GitHub + author's other apps ──────────────── */
.ev-footer{ display:flex; flex-wrap:wrap; align-items:center; justify-content:center; gap:8px 18px;
  margin:30px auto 6px; padding:18px 16px 4px; font-size:13.5px; color:var(--muted);
  border-top:1px solid var(--line);}
.ev-footer .ev-gh{ display:inline-flex; align-items:center; gap:6px; color:var(--jade-d);
  font-weight:600; text-decoration:none;}
.ev-footer .ev-gh:hover{ text-decoration:underline;}
.ev-footer .ev-more{ color:var(--muted);}
.ev-footer .ev-more a{ color:var(--jade-d); text-decoration:none; font-weight:500;}
.ev-footer .ev-more a:hover{ text-decoration:underline;}

/* ── responsive: stack columns on narrow screens ───────── */
@media (max-width:860px){
  .ev-row{ flex-direction:column!important;}
  .ev-steps{ flex-direction:column; gap:8px;}
  .ev-promise{ font-size:31px;}
  .ev-mark{ font-size:200px; bottom:-52px;}
  .ev-hero{ padding:24px 22px;}
  .gradio-container{ padding:0 14px 40px!important;}
}
"""


def _header_html(tb):
    gpu = tts_engine.is_gpu()
    dot = "live" if gpu else "idle"
    status = i18n.t(tb, "banner.gpu") if gpu else i18n.t(tb, "banner.cpu")
    promise = i18n.t(tb, "hero.promise")
    trust = i18n.t(tb, "hero.trust")
    return f"""
<header class="ev-hero">
  <span class="ev-mark" aria-hidden="true">声</span>
  <div class="ev-hero-row">
    <div class="ev-brand"><span class="ev-logo">易声</span><span class="ev-en">EASYVOICE</span></div>
    <div class="ev-hero-right">
      <div class="ev-lang" title="界面语言 / Interface language">
        <a class="lang-zh" href="?__lang=zh&amp;__theme=light">简</a>
        <a class="lang-zhhant" href="?__lang=zh-Hant&amp;__theme=light">繁</a>
        <a class="lang-en" href="?__lang=en&amp;__theme=light">EN</a>
      </div>
      <div class="ev-status"><span class="ev-dot {dot}"></span>{status}</div>
    </div>
  </div>
  <h1 class="ev-promise"><span class="ev-qk">「</span>{promise}<span class="ev-qk">」</span></h1>
  <p class="ev-trust">{trust}</p>
</header>"""


def _steps_html(tb):
    steps = [
        ("1", i18n.t(tb, "step.pick"),  i18n.t(tb, "step.pick.sub")),
        ("2", i18n.t(tb, "step.write"), i18n.t(tb, "step.write.sub")),
        ("3", i18n.t(tb, "step.play"),  i18n.t(tb, "step.play.sub")),
    ]
    items = "".join(
        f'<div class="ev-step"><div class="n">{n}</div>'
        f'<div class="tx"><div class="t">{t}</div><div class="s">{s}</div></div></div>'
        for n, t, s in steps
    )
    return f'<div class="ev-steps">{items}</div>'


def _eyebrow(text):
    return f'<div class="ev-eyebrow">{text}</div>'


# ── 页脚：GitHub + 作者其他开源应用 ───────────────────────────────────────
GITHUB_URL = "https://github.com/rockbenben/easyvoice"
_MORE_APPS = [
    # (简体, 繁體, English, url) — names follow the UI language
    ("AI 工具箱", "AI 工具箱", "AI Toolbox", "https://tools.newzone.top"),
    ("AI 绘图提示词", "AI 繪圖提示詞", "AI Image Prompts", "https://prompt.newzone.top"),
    ("AI 思想家圆桌", "AI 思想家圓桌", "AI Thinkers' Roundtable", "https://talk.newzone.top"),
    ("AI Short", "AI Short", "AI Short", "https://www.aishort.top"),
]
_GH_SVG = (
    '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" fill="currentColor">'
    '<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19'
    '-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52'
    '-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2'
    '-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82'
    '.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08'
    ' 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01'
    ' 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
)


def _footer_html(loc="zh-Hans"):
    idx = 2 if loc == "en" else (1 if loc == "zh-Hant" else 0)
    label = "More by me" if loc == "en" else "更多作品"
    sep = ":&nbsp;" if loc == "en" else "："
    apps = " · ".join(
        f'<a href="{a[3]}" target="_blank" rel="noopener">{a[idx]}</a>' for a in _MORE_APPS
    )
    return (
        '<div class="ev-footer">'
        f'<a class="ev-gh" href="{GITHUB_URL}" target="_blank" rel="noopener">{_GH_SVG} GitHub</a>'
        f'<span class="ev-more">{label}{sep}{apps}</span>'
        '</div>'
    )


# ── gr.I18n：界面按浏览器语言自动本地化（简体 / 繁体 / English）─────────────
# 浏览器 locale → 文案表。显式给出 zh-TW/zh-HK，繁体系统才会命中繁体（实测
# zh-Hant 单键不会被 zh-TW 命中）。整块 HTML(hero/steps/eyebrow)按 locale 整体替换。
_I18N_LOCALES = {
    "en": "en",
    "zh": "zh-Hans", "zh-CN": "zh-Hans", "zh-SG": "zh-Hans",
    "zh-Hant": "zh-Hant", "zh-TW": "zh-Hant", "zh-HK": "zh-Hant", "zh-MO": "zh-Hant",
}


def _build_i18n() -> gr.I18n:
    trans = {}
    for loc, fname in _I18N_LOCALES.items():
        tb = i18n.load(fname)
        d = dict(tb)                          # 所有文案键（组件 label/info/button/guide）
        d["_hero"]       = _header_html(tb)   # 整块 HTML，按 locale 整体切换
        d["_steps"]      = _steps_html(tb)
        d["_eb_setup"]   = _eyebrow(i18n.t(tb, "sec.setup"))
        d["_eb_compose"] = _eyebrow(i18n.t(tb, "sec.compose"))
        d["_eb_voadd"]   = _eyebrow(i18n.t(tb, "voice.add_title"))
        d["_eb_vomng"]   = _eyebrow(i18n.t(tb, "voice.manage_title"))
        d["_eb_psuse"]   = _eyebrow(i18n.t(tb, "preset.use_title"))
        d["_eb_pssave"]  = _eyebrow(i18n.t(tb, "preset.save_title"))
        trans[loc] = d
    return gr.I18n(**trans)


I18N = _build_i18n()


_STYLE_PARAMS = {
    "stable":  (0.5, 0.85),
    "natural": (0.9, 0.90),
    "lively":  (1.2, 0.95),
}


def _voice_choices():
    return [(v["name"], v["id"]) for v in voice_library.list_voices()]


# Output-language picker uses autonyms (each language in its own script) so it reads
# correctly regardless of UI locale — gr.I18n can't localize dropdown/radio choice labels.
_LANG_AUTONYM = {
    "auto": "Auto",
    "chinese": "中文", "english": "English", "japanese": "日本語", "korean": "한국어",
    "german": "Deutsch", "french": "Français", "russian": "Русский",
    "portuguese": "Português", "spanish": "Español", "italian": "Italiano",
}


def _lang_choices():
    # auto-detect 居首（qwen-tts 支持 'auto'，见 SPIKE §4），其余用各自语言的本名
    opts = [("🌐 Auto", "auto")]
    opts += [(_LANG_AUTONYM.get(l["code"], l["code"]), l["code"]) for l in config.SUPPORTED_LANGS]
    return opts


def do_generate(text, lang, voice_id, temperature=0.9, top_p=0.9, speed=1.0,
                top_k=50, repetition_penalty=1.0, max_new_tokens=2048, seed=0,
                request: gr.Request = None, progress=gr.Progress()):
    if not text or not voice_id:
        raise gr.Error(i18n.t(_req_tb(request), "err.need_text_voice"))
    try:
        ref = voice_library.get_audio_path(voice_id)
    except KeyError:
        raise gr.Error(i18n.t(_req_tb(request), "err.voice_missing"))
    ref_text = voice_library.get_ref_text(voice_id)
    tb = _req_tb(request)

    def cb(done, total):                                # 实时进度："已生成 X/Y 字"
        try:
            progress(done / total if total else 0,
                     desc=i18n.t(tb, "prog.chars").replace("{d}", str(done)).replace("{t}", str(total)))
        except Exception:
            pass

    return tts_engine.synthesize(
        text, lang, ref, temperature, top_p, speed,
        top_k=int(top_k), repetition_penalty=repetition_penalty,
        max_new_tokens=int(max_new_tokens), ref_text=ref_text, seed=int(seed or 0),
        progress_cb=cb)


def do_apply_style(style):
    temp, tp = _STYLE_PARAMS.get(style, _STYLE_PARAMS["natural"])
    return temp, tp


_TOK_PER_SEC = 12.5   # Qwen3-TTS 12Hz：约 12.5 个音频 token / 秒
_TOK_WARN = 8192      # 超过约 11 分钟 → 给"较慢/建议分段"提醒(qwen-tts 自身无此提示)


def do_tok_estimate(tokens, tb_lang="zh-Hans"):
    """把最大生成长度(token)折算成预计语音时长，随滑块实时显示；超长时附带提醒。"""
    tb = i18n.load(tb_lang)
    n = float(tokens or 0)
    mins = (n / _TOK_PER_SEC) / 60.0
    txt = i18n.t(tb, "adv.tok_est").replace("{m}", f"{mins:.1f}")
    if n > _TOK_WARN:
        return "⚠️ " + txt + " · " + i18n.t(tb, "adv.tok_slow")
    return txt


def _loc_tok_estimate(tokens, request: gr.Request):
    return do_tok_estimate(tokens, _lang_from_request(request))


def do_add_voice(name, ref_path, ref_text="", bump=0, request: gr.Request = None):
    if not name or not name.strip():
        raise gr.Error(i18n.t(_req_tb(request), "err.need_voice_name"))
    if not ref_path:
        raise gr.Error(i18n.t(_req_tb(request), "err.need_ref_audio"))
    voice_library.add_voice(name, ref_path, ref_text)   # front=True → 新音色置顶
    return gr.update(choices=_voice_choices()), bump + 1  # -> (配音 voice_dd, _bump 触发重渲染)


# ── 音色库逐行管理(gr.render 内联调用) ──
def do_voice_save_edit(voice_id, name, bump):
    """编辑态保存：只改音色名称(非空才改)；回传 bump+1 重渲染、清编辑态、刷新 voice_dd。"""
    nm = (name or "").strip()
    if nm:
        voice_library.rename_voice(voice_id, nm)
    return bump + 1, None, gr.update(choices=_voice_choices())


def do_voice_move(voice_id, delta, bump):
    voice_library.move_voice(voice_id, delta)
    return bump + 1, gr.update(choices=_voice_choices())


def do_voice_delete(voice_id, bump):
    voice_library.delete_voice(voice_id)
    return bump + 1, None, gr.update(choices=_voice_choices())  # 重渲染 / 清待确认 / 刷新 voice_dd


def do_save_preset(name, lang, voice_id, temperature, top_p, speed, pbump=0,
                   request: gr.Request = None):
    if not name or not name.strip():
        raise gr.Error(i18n.t(_req_tb(request), "err.need_preset_name"))
    presets.save_preset(name, {
        "lang": lang, "voice_id": voice_id,
        "temperature": temperature, "top_p": top_p, "speed": speed,
    })
    return gr.update(choices=presets.list_presets()), pbump + 1  # -> (配音方案下拉, 管理列表重渲染)


def do_preset_delete(name, pbump):
    presets.delete_preset(name)
    return pbump + 1, None, gr.update(choices=presets.list_presets())  # 重渲染 / 清待确认 / 刷新下拉


def do_apply_preset(name, request: gr.Request = None):
    if not name:
        raise gr.Error(i18n.t(_req_tb(request), "err.need_preset"))
    p = presets.get_preset(name)
    return (
        p.get("lang"),
        p.get("voice_id"),
        p.get("speed", 1.0),
        p.get("temperature", 0.9),
        p.get("top_p", 0.9),
    )


def _temp_to_style_key(t):
    if t <= 0.65:
        return "stable"
    if t <= 1.0:
        return "natural"
    return "lively"


def do_preset_summary(name, tb_lang="zh-Hans"):
    tb = i18n.load(tb_lang)
    if not name:
        return ""
    try:
        p = presets.get_preset(name)
    except Exception:
        return ""
    # resolve voice id -> name
    vname = next(
        (v["name"] for v in voice_library.list_voices() if v["id"] == p.get("voice_id")),
        p.get("voice_id", ""),
    )
    # resolve language code -> label via SUPPORTED_LANGS/i18n
    lcode = p.get("lang", "")
    llabel = next(
        (i18n.t(tb, l["label_key"]) for l in config.SUPPORTED_LANGS if l["code"] == lcode),
        _LANG_AUTONYM.get(lcode, lcode),
    )
    stylekey = _temp_to_style_key(p.get("temperature", 0.9))
    slabel = i18n.t(tb, "style." + stylekey)
    speed = p.get("speed", 1.0)
    return (
        f"**{i18n.t(tb, 'summary.lang')}**：{llabel}　｜　"
        f"**{i18n.t(tb, 'summary.voice')}**：{vname}　｜　"
        f"**{i18n.t(tb, 'summary.style')}**：{slabel}　｜　"
        f"**{i18n.t(tb, 'summary.speed')}**：{speed}×"
    )


def _style_choices(tb):
    return [
        (i18n.t(tb, "style.stable"), "stable"),
        (i18n.t(tb, "style.natural"), "natural"),
        (i18n.t(tb, "style.lively"), "lively"),
    ]


def _lang_from_request(request) -> str:
    """决定本地化语言：① 手动切换 ?__lang=（界面语言选择器写入）优先；
    ② 否则按访客浏览器 Accept-Language。用于 gr.I18n 覆盖不到的下拉/单选 choice 与动态摘要。"""
    # ① manual override
    try:
        q = (request.query_params.get("__lang") or "").lower()
    except Exception:
        q = ""
    if q.startswith("en"):
        return "en"
    if q.startswith("zh"):
        return "zh-Hant" if ("hant" in q or q in ("zh-tw", "zh-hk", "zh-mo")) else "zh-Hans"
    # ② browser Accept-Language
    try:
        al = (request.headers.get("accept-language") or "").lower()
    except Exception:
        al = ""
    if al.startswith("en"):
        return "en"
    if al.startswith("zh"):
        if any(t in al[:16] for t in ("hant", "zh-tw", "zh-hk", "zh-mo")):
            return "zh-Hant"
        return "zh-Hans"
    return "zh-Hans"


def _req_tb(request):
    """当前请求的文案表（测试中 request=None → 简体）；用于本地化处理器内的 gr.Error。"""
    return i18n.load(_lang_from_request(request) if request is not None else "zh-Hans")


def _run_generate(text, lang, voice_id, temperature=0.9, top_p=0.9, speed=1.0,
                  top_k=50, repetition_penalty=1.0, max_new_tokens=2048, seed=0,
                  request: gr.Request = None, progress=gr.Progress()):
    """生成包装(生成器)：先禁用按钮显示"生成中" → 跑 do_generate → 无论成功或出错都复位按钮。
    出错时先 yield 复位、再把 gr.Error 冒泡给前端弹窗。不能用 .then(复位)：异常后 .then 不执行，
    会把按钮永久卡在"生成中"禁用态(只能刷页恢复)。"""
    tb = _req_tb(request)
    busy = gr.update(value=i18n.t(tb, "btn.generating"), interactive=False)
    idle = gr.update(value=i18n.t(tb, "btn.generate"), interactive=True)
    yield busy, gr.update()
    try:
        audio = do_generate(text, lang, voice_id, temperature, top_p, speed,
                            top_k, repetition_penalty, max_new_tokens, seed,
                            request=request, progress=progress)
    except Exception:
        yield idle, gr.update()                # 出错也复位按钮
        raise                                   # 仍把错误冒泡 → 前端弹窗
    yield idle, audio


def _run_subtitle_dub(file_path, voice_id, lang,
                      request: gr.Request = None, progress=gr.Progress()):
    """字幕配音包装(生成器)：同 _run_generate，出错也复位按钮，避免卡死在"生成中"。"""
    tb = _req_tb(request)
    busy = gr.update(value=i18n.t(tb, "btn.generating"), interactive=False)
    idle = gr.update(value=i18n.t(tb, "sub.generate"), interactive=True)
    yield busy, gr.update(), gr.update()
    try:
        audio, srt = do_subtitle_dub(file_path, voice_id, lang,
                                     request=request, progress=progress)
    except Exception:
        yield idle, gr.update(), gr.update()    # 出错也复位按钮
        raise
    yield idle, audio, srt


def do_subtitle_preview(file_path, request: gr.Request = None):
    if not file_path:
        return ""
    try:
        content = open(file_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    cues = tts_engine.parse_subtitles(content)
    tb = _req_tb(request)
    if not cues:
        return i18n.t(tb, "err.no_cues")
    mins = max(c["end"] for c in cues) / 60.0
    return i18n.t(tb, "sub.parsed").replace("{n}", str(len(cues))).replace("{m}", f"{mins:.1f}")


def do_subtitle_dub(file_path, voice_id, lang, request: gr.Request = None, progress=gr.Progress()):
    if not file_path:
        raise gr.Error(i18n.t(_req_tb(request), "err.need_subtitle"))
    try:
        ref = voice_library.get_audio_path(voice_id)        # None/失效 → KeyError
    except KeyError:
        raise gr.Error(i18n.t(_req_tb(request), "err.voice_missing"))
    content = open(file_path, encoding="utf-8", errors="ignore").read()
    cues = tts_engine.parse_subtitles(content)
    if not cues:
        raise gr.Error(i18n.t(_req_tb(request), "err.no_cues"))
    ref_text = voice_library.get_ref_text(voice_id)
    tb = _req_tb(request)

    def cb(done, total):                                # 实时进度："已合成 X/Y 条"
        try:
            progress(done / total if total else 0,
                     desc=i18n.t(tb, "prog.cues").replace("{d}", str(done)).replace("{t}", str(total)))
        except Exception:
            pass

    return tts_engine.synthesize_subtitles(cues, lang, ref, ref_text=ref_text, progress_cb=cb)


def build_ui(lang: str = "zh-Hans") -> gr.Blocks:
    config.ensure_dirs()
    tb = i18n.load(lang)
    _first_voice = next((v["id"] for v in voice_library.list_voices()), None)
    _preset_names = presets.list_presets()
    _chinese_default = "新闻播报（中文·稳定）"
    _default_preset = (_chinese_default if _chinese_default in _preset_names
                       else (_preset_names[0] if _preset_names else None))
    with gr.Blocks(title="易声 EasyVoice") as demo:   # 标签标题：gr.I18n 不本地化 <title>，用固定品牌名
        hero = gr.HTML(I18N("_hero"))
        _pbump = gr.State(0)        # 常用方案逐行列表重渲染信号(+1 触发)
        _ppending = gr.State(None)  # 待二次确认删除的方案名
        with gr.Tabs(elem_classes=["ev-tabs"]):
            # ── 配音: settings | compose + result ─────────────────────
            with gr.Tab(I18N("tab.tts")) as tab_tts:
                steps = gr.HTML(I18N("_steps"))
                with gr.Row(elem_classes=["ev-row"]):
                    with gr.Column(scale=2, min_width=320):
                        with gr.Group(elem_classes=["ev-card"]):
                            eb_setup = gr.HTML(I18N("_eb_setup"))
                            dub_preset = gr.Dropdown(_preset_names, value=_default_preset,
                                                     label=I18N("preset.quick"))
                            lang_dd = gr.Dropdown(_lang_choices(), label=I18N("field.lang"),
                                                  info=I18N("field.lang_info"), value="chinese")
                            voice_dd = gr.Dropdown(_voice_choices(), label=I18N("field.voice"),
                                                   info=I18N("field.voice_info"), value=_first_voice)
                            style_radio = gr.Radio(
                                choices=_style_choices(tb), value="natural",
                                label=I18N("style.title"), info=I18N("style.info"),
                                elem_classes=["ev-style"],
                            )
                            speed = gr.Slider(0.5, 2.0, value=1.0, step=0.1,
                                              label=I18N("field.speed"), info=I18N("field.speed_info"))
                            with gr.Accordion(I18N("adv.title"), open=False,
                                              elem_classes=["ev-acc"]) as accordion:
                                adv_hint = gr.Markdown(I18N("adv.hint"),
                                                       elem_classes=["ev-acc-hint"])
                                temperature = gr.Slider(0.1, 1.5, value=0.9, step=0.05,
                                                        label=I18N("adv.temperature"),
                                                        info=I18N("adv.temperature_info"))
                                top_p = gr.Slider(0.1, 1.0, value=0.9, step=0.05,
                                                  label=I18N("adv.top_p"), info=I18N("adv.top_p_info"))
                                top_k = gr.Slider(1, 100, value=50, step=1,
                                                  label=I18N("adv.top_k"), info=I18N("adv.top_k_info"))
                                rep_pen = gr.Slider(1.0, 2.0, value=1.0, step=0.05,
                                                    label=I18N("adv.rep_pen"),
                                                    info=I18N("adv.rep_pen_info"))
                                max_tokens = gr.Slider(512, 65536, value=2048, step=256,
                                                       label=I18N("adv.max_tokens"),
                                                       info=I18N("adv.max_tokens_info"))
                                tok_est = gr.Markdown(do_tok_estimate(2048, lang),
                                                      elem_classes=["ev-tokest"])
                                seed_in = gr.Number(value=0, precision=0, minimum=0,
                                                    label=I18N("adv.seed"), info=I18N("adv.seed_info"))
                            dub_pname = gr.Textbox(label=I18N("preset.name"),
                                                   placeholder=I18N("preset.name_ph"))
                            dub_save = gr.Button(I18N("preset.save"))
                    with gr.Column(scale=3, min_width=360):
                        with gr.Group(elem_classes=["ev-card"]):
                            eb_compose = gr.HTML(I18N("_eb_compose"))
                            text_in = gr.Textbox(label=I18N("field.text"),
                                                 placeholder=I18N("field.text_ph"), lines=10)
                            gen = gr.Button(I18N("btn.generate"), variant="primary",
                                            elem_id="ev-generate")
                            audio_out = gr.Audio(label=I18N("field.result"), elem_classes=["ev-audio"])
                style_radio.change(do_apply_style, style_radio, [temperature, top_p],
                                   show_progress="hidden")
                max_tokens.change(_loc_tok_estimate, max_tokens, tok_est, show_progress="hidden")
                gen.click(_run_generate,                                    # 禁用→生成→复位(出错也复位)
                          [text_in, lang_dd, voice_dd, temperature, top_p, speed,
                           top_k, rep_pen, max_tokens, seed_in],
                          [gen, audio_out])
                dub_preset.change(do_apply_preset, [dub_preset],
                                  [lang_dd, voice_dd, speed, temperature, top_p],
                                  show_progress="hidden")
                dub_save.click(do_save_preset,
                               [dub_pname, lang_dd, voice_dd, temperature, top_p, speed, _pbump],
                               [dub_preset, _pbump])
            # ── 我的音色库: add | manage ──────────────────────────────
            with gr.Tab(I18N("tab.voices")) as tab_voices:
                voice_hint = gr.Markdown(I18N("voice.hint"), elem_classes=["ev-guide"])
                with gr.Row(elem_classes=["ev-row"]):
                    with gr.Column(min_width=320):
                        with gr.Group(elem_classes=["ev-card"]):
                            eb_voadd = gr.HTML(I18N("_eb_voadd"))
                            vname = gr.Textbox(label=I18N("voice.name"),
                                               placeholder=I18N("voice.name_ph"))
                            vref = gr.Audio(label=I18N("voice.ref"), type="filepath",
                                            elem_classes=["ev-audio"])
                            vref_text = gr.Textbox(label=I18N("voice.ref_text"),
                                                   info=I18N("voice.ref_text_info"), lines=2)
                            vadd = gr.Button(I18N("voice.add"), variant="primary")
                    with gr.Column(min_width=320):
                        with gr.Group(elem_classes=["ev-card"]):
                            eb_vomng = gr.HTML(I18N("_eb_vomng"))
                            manage_hint = gr.Markdown(I18N("voice.manage_hint"),
                                                      elem_classes=["ev-guide"])
                            _bump = gr.State(0)          # +1 触发整列表重渲染
                            _pending = gr.State(None)    # 待二次确认删除的音色 id
                            _vediting = gr.State(None)   # 正在编辑的音色 id
                            _vloc = gr.State("zh-Hans")  # 行内文案语言(load 时由 relabel 写入)

                            @gr.render(inputs=[_bump, _pending, _vediting, _vloc],
                                       triggers=[tab_voices.select, _bump.change,
                                                 _pending.change, _vediting.change])
                            def _render_voices(_b, pending, editing, vloc):
                                vtb = i18n.load(vloc or "zh-Hans")
                                voices = voice_library.list_voices()
                                if not voices:
                                    gr.Markdown(i18n.t(vtb, "voice.empty"), elem_classes=["ev-guide"])
                                    return
                                n = len(voices)
                                for i, v in enumerate(voices):
                                    vid = v["id"]
                                    if vid == pending:                       # 删除二次确认
                                        with gr.Row(elem_classes=["ev-vrow", "ev-vrow-del"]):
                                            gr.Markdown("**" + v["name"] + "** — "
                                                        + i18n.t(vtb, "voice.del_confirm"))
                                            yes = gr.Button(i18n.t(vtb, "voice.del_yes"),
                                                            variant="stop", scale=1, min_width=72)
                                            no = gr.Button(i18n.t(vtb, "voice.del_no"),
                                                           scale=1, min_width=72)
                                        yes.click(lambda b, _id=vid: do_voice_delete(_id, b),
                                                  [_bump], [_bump, _pending, voice_dd])
                                        no.click(lambda: None, None, [_pending])
                                    elif vid == editing:                     # 编辑态：只改名称(按钮另起一行)
                                        with gr.Group(elem_classes=["ev-editbox"]):
                                            e_nm = gr.Textbox(v["name"], show_label=False,
                                                              container=False, elem_classes=["ev-edit"])
                                            with gr.Row(elem_classes=["ev-editbtns"]):
                                                sv = gr.Button(i18n.t(vtb, "edit.save"),
                                                               variant="primary", scale=1, min_width=72)
                                                cx = gr.Button(i18n.t(vtb, "edit.cancel"),
                                                               scale=1, min_width=72)
                                        sv.click(lambda nm_, b, _id=vid: do_voice_save_edit(_id, nm_, b),
                                                 [e_nm, _bump], [_bump, _vediting, voice_dd])
                                        cx.click(lambda: None, None, [_vediting])
                                    else:                                    # 显示态：名字(文本) + ✎/调序/删除
                                        with gr.Row(elem_classes=["ev-vrow"]):
                                            gr.Markdown(v["name"], elem_classes=["ev-vname"])
                                            ed = gr.Button("✎", scale=0, min_width=44)
                                            up = gr.Button("↑", scale=0, min_width=44, interactive=(i > 0))
                                            dn = gr.Button("↓", scale=0, min_width=44, interactive=(i < n - 1))
                                            dl = gr.Button("🗑", scale=0, min_width=44)
                                        ed.click(lambda _id=vid: _id, None, [_vediting])
                                        up.click(lambda b, _id=vid: do_voice_move(_id, -1, b),
                                                 [_bump], [_bump, voice_dd])
                                        dn.click(lambda b, _id=vid: do_voice_move(_id, 1, b),
                                                 [_bump], [_bump, voice_dd])
                                        dl.click(lambda _id=vid: _id, None, [_pending])
                vadd.click(do_add_voice, [vname, vref, vref_text, _bump], [voice_dd, _bump])
            # ── 常用方案: 逐行管理(套用/保存在『配音』里，这里只整理) ──────
            with gr.Tab(I18N("tab.presets")) as tab_presets:
                preset_guide = gr.Markdown(I18N("guide.presets"), elem_classes=["ev-guide"])
                with gr.Group(elem_classes=["ev-card"]):

                    @gr.render(inputs=[_pbump, _ppending, _vloc],
                               triggers=[tab_presets.select, _pbump.change, _ppending.change])
                    def _render_presets(_b, pending, vloc):
                        ptb = i18n.load(vloc or "zh-Hans")
                        names = presets.list_presets()
                        if not names:
                            gr.Markdown(i18n.t(ptb, "preset.empty"), elem_classes=["ev-guide"])
                            return
                        for name in names:
                            if name == pending:                      # 删除二次确认
                                with gr.Row(elem_classes=["ev-vrow", "ev-vrow-del"]):
                                    gr.Markdown("**" + name + "** — " + i18n.t(ptb, "voice.del_confirm"))
                                    yes = gr.Button(i18n.t(ptb, "voice.del_yes"),
                                                    variant="stop", scale=1, min_width=72)
                                    no = gr.Button(i18n.t(ptb, "voice.del_no"), scale=1, min_width=72)
                                yes.click(lambda b, _n=name: do_preset_delete(_n, b),
                                          [_pbump], [_pbump, _ppending, dub_preset])
                                no.click(lambda: None, None, [_ppending])
                            else:                                    # 显示态：名字 + 摘要 + 删除(方案只删不改)
                                with gr.Row(elem_classes=["ev-vrow"]):
                                    gr.Markdown(name, elem_classes=["ev-vname"])
                                    dl = gr.Button("🗑", scale=0, min_width=44)
                                gr.Markdown(do_preset_summary(name, vloc),
                                            elem_classes=["ev-readout", "ev-prow-sum"])
                                dl.click(lambda _n=name: _n, None, [_ppending])
            # ── 字幕配音: 上传字幕 → 按时间轴生成 ─────────────────────────
            with gr.Tab(I18N("tab.subtitle")) as tab_subtitle:
                sub_guide = gr.Markdown(I18N("sub.guide"), elem_classes=["ev-guide"])
                with gr.Row(elem_classes=["ev-row"]):
                    with gr.Column(scale=2, min_width=320):
                        with gr.Group(elem_classes=["ev-card"]):
                            sub_file = gr.File(label=I18N("sub.file"), file_count="single",
                                               type="filepath",
                                               file_types=[".srt", ".vtt", ".lrc", ".txt"])
                            sub_preview = gr.Markdown("", elem_classes=["ev-readout"])
                            sub_voice = gr.Dropdown(_voice_choices(), label=I18N("field.voice"),
                                                    info=I18N("field.voice_info"), value=_first_voice)
                            sub_lang = gr.Dropdown(_lang_choices(), label=I18N("field.lang"),
                                                   info=I18N("field.lang_info"), value="chinese")
                    with gr.Column(scale=3, min_width=360):
                        with gr.Group(elem_classes=["ev-card"]):
                            sub_gen = gr.Button(I18N("sub.generate"), variant="primary",
                                                elem_id="ev-subgen")
                            sub_audio = gr.Audio(label=I18N("field.result"), elem_classes=["ev-audio"])
                            sub_srt = gr.File(label=I18N("sub.srt"))
                sub_file.change(do_subtitle_preview, sub_file, sub_preview, show_progress="hidden")
                tab_subtitle.select(lambda: gr.update(choices=_voice_choices()), None, sub_voice,
                                    show_progress="hidden")
                sub_gen.click(_run_subtitle_dub,                            # 禁用→生成→复位(出错也复位)
                              [sub_file, sub_voice, sub_lang],
                              [sub_gen, sub_audio, sub_srt])
        footer = gr.HTML(_footer_html(lang))

        # ── 界面语言：手动切换(?__lang=)或浏览器自动，在 load 时服务端整体重排 ──
        # gr.I18n 运行时无法改 locale，故用确定性的服务端 relabel 覆盖全部组件（含 Tab 标签）。
        _relabel_targets = [
            hero, steps, eb_setup, eb_compose, eb_voadd, eb_vomng,
            tab_tts, tab_voices, tab_presets, tab_subtitle,
            lang_dd, voice_dd, style_radio, speed, accordion, adv_hint, temperature, top_p,
            top_k, rep_pen, max_tokens, tok_est, seed_in,
            text_in, gen, audio_out, voice_hint,
            vname, vref, vref_text, vadd, manage_hint, _vloc,
            preset_guide, dub_preset, dub_pname, dub_save,
            sub_guide, sub_file, sub_voice, sub_lang, sub_gen, sub_audio, sub_srt,
            footer,
        ]

        def _relabel(request: gr.Request):
            loc = _lang_from_request(request)
            t = i18n.load(loc)

            def L(k):
                return i18n.t(t, k)

            return {
                hero: gr.update(value=_header_html(t)),
                steps: gr.update(value=_steps_html(t)),
                eb_setup: gr.update(value=_eyebrow(L("sec.setup"))),
                eb_compose: gr.update(value=_eyebrow(L("sec.compose"))),
                eb_voadd: gr.update(value=_eyebrow(L("voice.add_title"))),
                eb_vomng: gr.update(value=_eyebrow(L("voice.manage_title"))),
                tab_tts: gr.update(label=L("tab.tts")),
                tab_voices: gr.update(label=L("tab.voices")),
                tab_presets: gr.update(label=L("tab.presets")),
                tab_subtitle: gr.update(label=L("tab.subtitle")),
                lang_dd: gr.update(label=L("field.lang"), info=L("field.lang_info")),
                voice_dd: gr.update(label=L("field.voice"), info=L("field.voice_info")),
                style_radio: gr.update(label=L("style.title"), info=L("style.info"),
                                       choices=_style_choices(t)),
                speed: gr.update(label=L("field.speed"), info=L("field.speed_info")),
                accordion: gr.update(label=L("adv.title")),
                adv_hint: gr.update(value=L("adv.hint")),
                temperature: gr.update(label=L("adv.temperature"), info=L("adv.temperature_info")),
                top_p: gr.update(label=L("adv.top_p"), info=L("adv.top_p_info")),
                top_k: gr.update(label=L("adv.top_k"), info=L("adv.top_k_info")),
                rep_pen: gr.update(label=L("adv.rep_pen"), info=L("adv.rep_pen_info")),
                max_tokens: gr.update(label=L("adv.max_tokens"), info=L("adv.max_tokens_info")),
                tok_est: gr.update(value=do_tok_estimate(2048, loc)),
                seed_in: gr.update(label=L("adv.seed"), info=L("adv.seed_info")),
                text_in: gr.update(label=L("field.text"), placeholder=L("field.text_ph")),
                gen: gr.update(value=L("btn.generate")),
                audio_out: gr.update(label=L("field.result")),
                voice_hint: gr.update(value=L("voice.hint")),
                vname: gr.update(label=L("voice.name"), placeholder=L("voice.name_ph")),
                vref: gr.update(label=L("voice.ref")),
                vref_text: gr.update(label=L("voice.ref_text"), info=L("voice.ref_text_info")),
                vadd: gr.update(value=L("voice.add")),
                manage_hint: gr.update(value=L("voice.manage_hint")),
                _vloc: loc,
                preset_guide: gr.update(value=L("guide.presets")),
                dub_preset: gr.update(label=L("preset.quick")),
                dub_pname: gr.update(label=L("preset.name"), placeholder=L("preset.name_ph")),
                dub_save: gr.update(value=L("preset.save")),
                sub_guide: gr.update(value=L("sub.guide")),
                sub_file: gr.update(label=L("sub.file")),
                sub_voice: gr.update(label=L("field.voice"), info=L("field.voice_info")),
                sub_lang: gr.update(label=L("field.lang"), info=L("field.lang_info")),
                sub_gen: gr.update(value=L("sub.generate")),
                sub_audio: gr.update(label=L("field.result")),
                sub_srt: gr.update(label=L("sub.srt")),
                footer: gr.update(value=_footer_html(loc)),
            }

        demo.load(_relabel, None, _relabel_targets, show_progress="hidden")
        demo.queue()
    return demo
