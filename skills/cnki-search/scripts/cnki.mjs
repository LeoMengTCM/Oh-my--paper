#!/usr/bin/env node
/**
 * cnki.mjs — CNKI（中国知网）检索客户端
 *
 * 通过本仓库已有的 CDP proxy（literature-pdf-ocr-library/scripts/cdp-proxy.mjs）驱动
 * 用户自己开着远程调试的 Chrome，天然携带登录态。没有 API，也不做请求伪造。
 *
 * 上游：https://github.com/cookjohn/cnki-skills（10 个 chrome-devtools MCP 技能）
 * 本文件把上游的 DOM 选择器与取数逻辑原样搬过来，只把传输层换成本仓库的 CDP proxy。
 *
 * 用法：
 *   node cnki.mjs status
 *   node cnki.mjs search --query "深度学习"
 *   node cnki.mjs advanced --query "脓毒症" --source CSSCI 北大核心 --from-year 2020
 *   node cnki.mjs parse
 *   node cnki.mjs pages --action next | --action page:3
 *   node cnki.mjs sort --by citations
 *   node cnki.mjs detail --url https://kns.cnki.net/kcms2/article/abstract?v=...
 *   node cnki.mjs export --indices 1,3,5 --mode gbt --out refs/cnki.gbt.txt
 *   node cnki.mjs journal --name "计算机学报"
 *   node cnki.mjs toc --journal "计算机学报" --year 2025 --issue 01
 *   node cnki.mjs download --format pdf
 *   node cnki.mjs collect --title "论文标题" --into .pipeline/literature/<corpus>/papers
 *
 * 输出：stdout 一律是 JSON。遇到验证码 / 未登录 / Chrome 未就绪时返回
 * `{"error": "...", "hint": "..."}` 并以退出码 2 结束，调用方据此暂停并请用户处理。
 */

import { spawn } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const SKILLS_ROOT = path.resolve(SCRIPT_DIR, "..", "..");
const PROXY_SCRIPT = path.join(
  SKILLS_ROOT,
  "literature-pdf-ocr-library",
  "scripts",
  "cdp-proxy.mjs",
);
const PROXY_PORT = Number(process.env.CDP_PROXY_PORT || 3456);
const PROXY = `http://127.0.0.1:${PROXY_PORT}`;

const URLS = {
  home: "https://www.cnki.net",
  search: "https://kns.cnki.net/kns8s/search",
  // 高级检索必须走旧版界面：新版（kns8s/AdvSearch）没有来源类别复选框
  advanced: "https://kns.cnki.net/kns/AdvSearch?classid=7NS01R8M",
  journalSearch: "https://navi.cnki.net/knavi",
  exportApi: "https://kns.cnki.net/dm8/API/GetExport",
};

const EXIT_NEEDS_USER = 2;

// ---------------------------------------------------------------- 参数解析

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      out._.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (key.startsWith("no-") || next === undefined || next.startsWith("--")) {
      out[key] = true;
      continue;
    }
    // 支持 --source A B C 这类多值参数
    const values = [next];
    while (argv[i + 2] !== undefined && !argv[i + 2].startsWith("--")) {
      values.push(argv[i + 2]);
      i += 1;
    }
    i += 1;
    out[key] = values.length === 1 ? values[0] : values;
  }
  return out;
}

/**
 * 取文本参数。多值（用户没加引号，如 `--query 深度学习 模型`）时用空格接回去，
 * 而不是只取第一个词、默默丢掉后半截。
 */
function argText(value) {
  if (value === undefined || value === true) return "";
  return Array.isArray(value) ? value.join(" ") : value;
}

function listOf(value) {
  if (value === undefined || value === true) return [];
  return Array.isArray(value) ? value : [value];
}

function emit(payload, exitCode = 0) {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  process.exit(exitCode);
}

function fail(error, hint) {
  emit({ error, hint }, EXIT_NEEDS_USER);
}

// ---------------------------------------------------------------- CDP proxy

async function proxyHealth() {
  try {
    const resp = await fetch(`${PROXY}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data?.connected ? data : null;
  } catch {
    return null;
  }
}

async function ensureProxy() {
  if (await proxyHealth()) return;

  if (!existsSync(PROXY_SCRIPT)) {
    fail(
      "找不到 cdp-proxy.mjs",
      `预期路径 ${PROXY_SCRIPT}，确认 literature-pdf-ocr-library 技能已随插件安装。`,
    );
  }

  const child = spawn(process.execPath, [PROXY_SCRIPT], {
    detached: true,
    stdio: "ignore",
  });
  child.unref();

  for (let i = 0; i < 12; i += 1) {
    await sleep(500);
    if (await proxyHealth()) return;
  }

  fail(
    "Chrome 远程调试未就绪",
    "CNKI 需要浏览器登录态，只能走 Chrome。请：①用 --remote-debugging-port=9222 启动 Chrome；" +
      "②在 Chrome 里打开 https://www.cnki.net 并登录；③重跑 " +
      "`bash .claude/skills/literature-pdf-ocr-library/scripts/check-deps.sh` 后重试。",
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function listPages() {
  const resp = await fetch(`${PROXY}/targets`);
  if (!resp.ok) throw new Error(`/targets 失败：HTTP ${resp.status}`);
  return resp.json();
}

async function openPage(url) {
  const resp = await fetch(`${PROXY}/new?url=${encodeURIComponent(url)}`);
  if (!resp.ok) throw new Error(`/new 失败：HTTP ${resp.status}`);
  const { targetId } = await resp.json();
  if (!targetId) throw new Error("/new 未返回 targetId");
  return targetId;
}

async function navigate(target, url) {
  await fetch(
    `${PROXY}/navigate?target=${encodeURIComponent(target)}&url=${encodeURIComponent(url)}`,
  );
}

/**
 * 取一个可用的 CNKI 标签页（保留登录态）。
 *
 * 只复用本技能自己开的那种页面（URL 前缀匹配 reusePrefix），绝不抢占用户正在看的
 * CNKI 标签；匹配不到就新开一个。`anyCnki` 用于 parse/pages/sort/export 这类
 * "操作当前结果页"的命令，此时确实需要回到已有的检索页。
 */
async function ensureCnkiTab({ reusePrefix, anyCnki = false, openUrl } = {}) {
  const pages = await listPages();

  if (reusePrefix) {
    const match = pages.find((p) => (p.url || "").startsWith(reusePrefix));
    if (match) return match.targetId;
  }
  if (anyCnki) {
    const cnki = pages.filter((p) => (p.url || "").includes("cnki.net"));
    // 检索工作站在 kns.cnki.net，优先回到它；期刊页在 navi.cnki.net，兜底
    const kns = cnki.filter((p) => /kns\.cnki\.net/.test(p.url || ""));
    const pool = kns.length ? kns : cnki;
    if (pool.length) return pool[pool.length - 1].targetId;
  }
  return openPage(openUrl || reusePrefix || URLS.home);
}

async function evalJs(target, expression) {
  const resp = await fetch(
    `${PROXY}/eval?target=${encodeURIComponent(target)}`,
    { method: "POST", body: expression },
  );
  const text = await resp.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(`/eval 返回非 JSON：${text.slice(0, 300)}`);
  }
  if (data.error) throw new Error(`页面脚本报错：${data.error}`);
  if (data.value !== undefined) return data.value;
  return data;
}

/** 验证码守卫：腾讯滑块只会在可见时挡路，隐藏的 SDK 预加载 DOM 不算。 */
async function captchaVisible(target) {
  return evalJs(
    target,
    `(() => { const el = document.querySelector('#tcaptcha_transform_dy');
       return !!(el && el.getBoundingClientRect().top >= 0); })()`,
  );
}

async function guardCaptcha(target) {
  if (await captchaVisible(target)) {
    fail(
      "captcha",
      "CNKI 正在显示滑块验证码。请在 Chrome 里手动完成拼图验证，完成后告诉我继续。",
    );
  }
}

// ---------------------------------------------------------------- 页面脚本

/** 解析当前结果页表格（上游 cnki-parse-results 的选择器，原样保留）。 */
const PARSE_RESULTS_JS = `(() => {
  const rows = document.querySelectorAll('.result-table-list tbody tr');
  const checkboxes = document.querySelectorAll('.result-table-list tbody input.cbItem');
  const papers = Array.from(rows).map((row, index) => {
    const nameCell = row.querySelector('td.name');
    const titleLink = nameCell?.querySelector('a.fz14');
    return {
      n: index + 1,
      title: titleLink?.innerText?.trim() || '',
      url: titleLink?.href || '',
      exportId: checkboxes[index]?.value || '',
      authors: Array.from(row.querySelectorAll('td.author a.KnowledgeNetLink') || [])
        .map(a => a.innerText?.trim()).filter(Boolean).join('; '),
      journal: row.querySelector('td.source a')?.innerText?.trim() || '',
      date: row.querySelector('td.date')?.innerText?.trim() || '',
      database: row.querySelector('td.data')?.innerText?.trim() || '',
      citations: row.querySelector('td.quote')?.innerText?.trim() || '',
      downloads: row.querySelector('td.download')?.innerText?.trim() || '',
      onlineFirst: !!nameCell?.querySelector('.marktip')
    };
  });
  return {
    total: document.querySelector('.pagerTitleCell')?.innerText?.match(/([\\d,]+)/)?.[1] || '0',
    page: document.querySelector('.countPageMark')?.innerText || '1/1',
    papers
  };
})()`;

const READY_RESULTS_JS = `document.body.innerText.includes('条结果')`;

// ---------------------------------------------------------------- 子命令

async function cmdStatus(args) {
  const health = await proxyHealth();
  if (!health) {
    emit(
      {
        chrome: false,
        proxy: false,
        hint: "CDP proxy 未运行或 Chrome 没开远程调试。运行 `bash .claude/skills/literature-pdf-ocr-library/scripts/check-deps.sh` 查看，或直接跑其他子命令（会自动拉起 proxy）。",
      },
      EXIT_NEEDS_USER,
    );
  }
  const pages = await listPages();
  const cnki = pages.filter((p) => (p.url || "").includes("cnki.net"));
  const result = {
    chrome: true,
    proxy: true,
    chromePort: health.chromePort,
    cnkiTabs: cnki.map((p) => ({ targetId: p.targetId, url: p.url, title: p.title })),
  };
  if (cnki.length) {
    result.captcha = await captchaVisible(cnki[0].targetId);
  } else {
    result.hint = "还没有 CNKI 标签页。检索类子命令会自动打开；下载前请先在 Chrome 里登录知网。";
  }
  emit(result);
}

async function cmdSearch(args) {
  const query = argText(args.query) || args._.join(" ");
  if (!query) fail("缺少 --query", '例：node cnki.mjs search --query "深度学习"');

  await ensureProxy();
  const target = await ensureCnkiTab({ reusePrefix: URLS.search });
  await navigate(target, URLS.search);

  const js = `(async () => {
    const query = ${JSON.stringify(query)};
    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        if (document.querySelector('input.search-input')) resolve();
        else if (++n > 30) reject(new Error('搜索框未出现'));
        else setTimeout(tick, 500);
      };
      tick();
    });

    const cap = document.querySelector('#tcaptcha_transform_dy');
    if (cap && cap.getBoundingClientRect().top >= 0) return { error: 'captcha' };

    const input = document.querySelector('input.search-input');
    input.value = query;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('input.search-btn')?.click();

    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        if (document.body.innerText.includes('条结果')) resolve();
        else if (++n > 40) reject(new Error('结果未返回'));
        else setTimeout(tick, 500);
      };
      tick();
    });

    const cap2 = document.querySelector('#tcaptcha_transform_dy');
    if (cap2 && cap2.getBoundingClientRect().top >= 0) return { error: 'captcha' };

    return ${PARSE_RESULTS_JS};
  })()`;

  const result = await evalJs(target, js);
  if (result?.error === "captcha") {
    fail("captcha", "CNKI 正在显示滑块验证码。请在 Chrome 里手动完成拼图验证，完成后告诉我继续。");
  }
  emit({ query, targetId: target, url: URLS.search, ...result });
}

const FIELD_TYPES = ["SU", "TI", "KY", "TKA", "AB", "AU", "FT"];
const SOURCE_TYPES = { SCI: "SCI", EI: "EI", 北大核心: "hx", 核心期刊: "hx", CSSCI: "CSSCI", CSCD: "CSCD" };

async function cmdAdvanced(args) {
  const query = argText(args.query) || args._.join(" ");
  if (!query) fail("缺少 --query", '例：node cnki.mjs advanced --query "脓毒症" --source CSSCI --from-year 2020');

  const field = argText(args.field) || "SU";
  if (!FIELD_TYPES.includes(field)) {
    fail(`不支持的 --field：${field}`, `可选：${FIELD_TYPES.join(" ")}（SU=主题 TI=篇名 KY=关键词 TKA=篇关摘 AB=摘要）`);
  }

  const sourceNames = listOf(args.source);
  const sourceIds = [];
  for (const name of sourceNames) {
    const id = SOURCE_TYPES[name];
    if (!id) {
      fail(`不支持的 --source：${name}`, `可选：${Object.keys(SOURCE_TYPES).join(" ")}`);
    }
    if (!sourceIds.includes(id)) sourceIds.push(id);
  }

  await ensureProxy();
  const target = await ensureCnkiTab({ reusePrefix: URLS.advanced });
  await navigate(target, URLS.advanced);

  const config = {
    query,
    fieldType: field,
    query2: argText(args.query2) || "",
    fieldType2: argText(args.field2) || "KY",
    rowLogic: argText(args.logic) || "AND",
    sourceTypes: sourceIds,
    startYear: argText(args["from-year"]) || "",
    endYear: argText(args["to-year"]) || "",
    author: argText(args.author) || "",
    journal: argText(args.journal) || "",
  };

  const js = `(async () => {
    const cfg = ${JSON.stringify(config)};

    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        if (document.querySelector('#txt_1_value1')) resolve();
        else if (++n > 30) reject(new Error('高级检索表单未出现'));
        else setTimeout(tick, 500);
      };
      tick();
    });

    const cap = document.querySelector('#tcaptcha_transform_dy');
    if (cap && cap.getBoundingClientRect().top >= 0) return { error: 'captcha' };

    const selects = Array.from(document.querySelectorAll('select')).filter(s => s.offsetParent !== null);

    if (cfg.sourceTypes.length > 0) {
      const gjAll = document.querySelector('#gjAll');
      if (gjAll && gjAll.checked) gjAll.click();
      for (const st of cfg.sourceTypes) {
        const cb = document.querySelector('#' + st);
        if (cb && !cb.checked) cb.click();
      }
    }

    selects[0].value = cfg.fieldType;
    selects[0].dispatchEvent(new Event('change', { bubbles: true }));
    const input = document.querySelector('#txt_1_value1');
    input.value = cfg.query;
    input.dispatchEvent(new Event('input', { bubbles: true }));

    if (cfg.query2) {
      selects[5].value = cfg.rowLogic;
      selects[5].dispatchEvent(new Event('change', { bubbles: true }));
      selects[6].value = cfg.fieldType2;
      selects[6].dispatchEvent(new Event('change', { bubbles: true }));
      const input2 = document.querySelector('#txt_2_value1');
      input2.value = cfg.query2;
      input2.dispatchEvent(new Event('input', { bubbles: true }));
    }

    if (cfg.author) {
      const el = document.querySelector('#au_1_value1');
      if (el) { el.value = cfg.author; el.dispatchEvent(new Event('input', { bubbles: true })); }
    }
    if (cfg.journal) {
      const el = document.querySelector('#magazine_value1');
      if (el) { el.value = cfg.journal; el.dispatchEvent(new Event('input', { bubbles: true })); }
    }
    if (cfg.startYear) { selects[14].value = cfg.startYear; selects[14].dispatchEvent(new Event('change', { bubbles: true })); }
    if (cfg.endYear) { selects[15].value = cfg.endYear; selects[15].dispatchEvent(new Event('change', { bubbles: true })); }

    document.querySelector('div.search')?.click();

    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        if (document.body.innerText.includes('条结果')) resolve();
        else if (++n > 40) reject(new Error('结果未返回'));
        else setTimeout(tick, 500);
      };
      setTimeout(tick, 2000);
    });

    const cap2 = document.querySelector('#tcaptcha_transform_dy');
    if (cap2 && cap2.getBoundingClientRect().top >= 0) return { error: 'captcha' };

    return ${PARSE_RESULTS_JS};
  })()`;

  const result = await evalJs(target, js);
  if (result?.error === "captcha") {
    fail("captcha", "CNKI 正在显示滑块验证码。请在 Chrome 里手动完成拼图验证，完成后告诉我继续。");
  }
  emit({
    query,
    field,
    sourceTypes: sourceNames,
    fromYear: config.startYear,
    toYear: config.endYear,
    targetId: target,
    ...result,
  });
}

async function cmdParse() {
  await ensureProxy();
  const target = await ensureCnkiTab({ anyCnki: true });
  await guardCaptcha(target);

  const ready = await evalJs(target, READY_RESULTS_JS);
  if (!ready) {
    fail(
      "当前不是检索结果页",
      "先跑 `node cnki.mjs search --query \"...\"`，或在 Chrome 里手动检索到结果页后再 parse。",
    );
  }
  emit(await evalJs(target, PARSE_RESULTS_JS));
}

async function cmdPages(args) {
  const action = argText(args.action) || args._[0];
  if (!action) fail("缺少 --action", "可选：next / prev / page:3");

  await ensureProxy();
  const target = await ensureCnkiTab({ anyCnki: true });
  await guardCaptcha(target);

  const js = `(async () => {
    const action = ${JSON.stringify(action)};
    const links = document.querySelectorAll('.pages a');
    const prevMark = document.querySelector('.countPageMark')?.innerText;

    if (action === 'next') {
      const el = Array.from(links).find(a => a.innerText.trim() === '下一页');
      if (!el) return { error: 'no_next_page' };
      el.click();
    } else if (action === 'prev' || action === 'previous') {
      const el = Array.from(links).find(a => a.innerText.trim() === '上一页');
      if (!el) return { error: 'no_previous_page' };
      el.click();
    } else {
      const num = String(action).replace(/\\D/g, '');
      const el = Array.from(links).find(a => a.innerText.trim() === num);
      if (!el) return { error: 'page_not_found', available: Array.from(links).map(a => a.innerText.trim()) };
      el.click();
    }

    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        const mark = document.querySelector('.countPageMark')?.innerText;
        if (mark && mark !== prevMark) resolve();
        else if (++n > 30) reject(new Error('翻页超时'));
        else setTimeout(tick, 500);
      };
      setTimeout(tick, 1000);
    });

    const cap = document.querySelector('#tcaptcha_transform_dy');
    if (cap && cap.getBoundingClientRect().top >= 0) return { error: 'captcha' };

    return ${PARSE_RESULTS_JS};
  })()`;

  const result = await evalJs(target, js);
  if (result?.error === "captcha") {
    fail("captcha", "CNKI 正在显示滑块验证码。请在 Chrome 里手动完成拼图验证，完成后告诉我继续。");
  }
  if (result?.error) fail(result.error, "确认当前停在检索结果页。");
  emit({ action, ...result });
}

const SORT_IDS = { relevance: "FFD", date: "PT", citations: "CF", downloads: "DFR", comprehensive: "ZH" };

async function cmdSort(args) {
  const by = argText(args.by) || args._[0];
  const sortId = SORT_IDS[by];
  if (!sortId) fail(`不支持的 --by：${by}`, `可选：${Object.keys(SORT_IDS).join(" ")}（相关度/发表时间/被引/下载/综合）`);

  await ensureProxy();
  const target = await ensureCnkiTab({ anyCnki: true });
  await guardCaptcha(target);

  const js = `(async () => {
    const li = document.querySelector('#orderList li#${sortId}');
    if (!li) return { error: 'sort_option_not_found' };
    const prevMark = document.querySelector('.countPageMark')?.innerText;
    li.click();

    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        const mark = document.querySelector('.countPageMark')?.innerText;
        if (mark && mark !== prevMark) resolve();
        else if (++n > 30) reject(new Error('排序超时'));
        else setTimeout(tick, 500);
      };
      setTimeout(tick, 1000);
    });

    const cap = document.querySelector('#tcaptcha_transform_dy');
    if (cap && cap.getBoundingClientRect().top >= 0) return { error: 'captcha' };

    return ${PARSE_RESULTS_JS};
  })()`;

  const result = await evalJs(target, js);
  if (result?.error === "captcha") {
    fail("captcha", "CNKI 正在显示滑块验证码。请在 Chrome 里手动完成拼图验证，完成后告诉我继续。");
  }
  if (result?.error) fail(result.error, "确认当前停在检索结果页（排序控件只在结果页有）。");
  emit({ sortedBy: by, ...result });
}

const DETAIL_JS = `(() => {
  const brief = document.querySelector('.brief');
  if (!brief) return { error: 'not_a_detail_page' };

  const title = brief.querySelector('h1')?.innerText?.trim()
    ?.replace(/\\s*附视频\\s*$/, '')
    ?.replace(/\\s*网络首发\\s*$/, '');

  const authorH3s = brief.querySelectorAll('h3.author');
  const authors = [];
  if (authorH3s[0]) {
    authorH3s[0].querySelectorAll('a').forEach(a => {
      const raw = a.innerText || '';
      const sup = raw.match(/(\\d+)$/);
      authors.push({ name: raw.replace(/\\d+$/, '').trim(), affiliationNum: sup ? sup[1] : '' });
    });
  }
  const affiliations = [];
  if (authorH3s.length > 1) {
    authorH3s[1].querySelectorAll('a').forEach(a => affiliations.push(a.innerText?.trim()));
  }

  const keywordsP = document.querySelector('p.keywords');

  return {
    title,
    authors,
    affiliations,
    abstract: document.querySelector('.abstract-text')?.innerText?.trim() || '',
    keywords: keywordsP ? Array.from(keywordsP.querySelectorAll('a')).map(a => a.innerText?.replace(/;$/, '').trim()) : [],
    fund: document.querySelector('p.funds')?.innerText?.trim() || '',
    classification: document.querySelector('.clc-code')?.innerText?.trim() || '',
    journal: document.querySelector('.doc-top a')?.innerText?.trim() || '',
    pubInfo: document.querySelector('.head-time')?.innerText?.trim() || '',
    onlineFirst: !!brief.querySelector('.icon-shoufa'),
    toc: document.querySelector('.catalog-list, .catalog-listDiv')?.innerText?.trim() || '',
    exportId: document.querySelector('#export-id')?.value || '',
    doi: document.body.innerText.match(/DOI[：:]\\s*(\\S+)/)?.[1] || '',
    issn: document.body.innerText.match(/ISSN[：:]\\s*(\\S+)/)?.[1] || '',
    pageUrl: location.href
  };
})()`;

async function cmdDetail(args) {
  const url = argText(args.url) || args._[0];

  await ensureProxy();
  const target = url
    ? await ensureCnkiTab({ reusePrefix: url })
    : await ensureCnkiTab({ anyCnki: true });
  if (url) await navigate(target, url);
  await guardCaptcha(target);

  const js = `(async () => {
    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        if (document.querySelector('.brief h1')) resolve();
        else if (++n > 30) reject(new Error('详情页未加载'));
        else setTimeout(tick, 500);
      };
      tick();
    });
    return ${DETAIL_JS};
  })()`;

  const result = await evalJs(target, js);
  if (result?.error === "not_a_detail_page") {
    fail("当前不是论文详情页", "请给 --url 参数，或在 Chrome 里打开一篇论文的详情页。");
  }
  emit(result);
}

async function cmdExport(args) {
  const indices = String(argText(args.indices) || "")
    .split(",")
    .map((s) => Number.parseInt(s.trim(), 10))
    .filter((n) => Number.isInteger(n) && n > 0);
  const mode = argText(args.mode) || "gbt";

  await ensureProxy();
  const target = await ensureCnkiTab({ anyCnki: true });
  await guardCaptcha(target);

  const js = `(async () => {
    const API_URL = ${JSON.stringify(URLS.exportApi)};
    const INDICES = ${JSON.stringify(indices)};
    const rows = document.querySelectorAll('.result-table-list tbody tr');
    const checkboxes = document.querySelectorAll('.result-table-list tbody input.cbItem');

    // 结果页：批量导出（checkbox value 就是详情页的 #export-id）
    if (checkboxes.length > 0) {
      const picked = INDICES.length
        ? INDICES.map(i => i - 1).filter(i => i >= 0 && i < checkboxes.length)
        : Array.from({ length: checkboxes.length }, (_, i) => i);

      const out = [];
      for (const i of picked) {
        const resp = await fetch(API_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            filename: checkboxes[i].value,
            displaymode: 'GBTREFER,elearning,EndNote',
            uniplatform: 'NZKPT'
          })
        });
        const data = await resp.json();
        if (data.code !== 1) { out.push({ n: i + 1, error: data.msg || 'export_failed' }); continue; }
        const item = { n: i + 1, pageUrl: rows[i]?.querySelector('td.name a.fz14')?.href || '' };
        for (const entry of data.data) item[entry.mode] = entry.value[0];
        item.issn = item.ENDNOTE?.match(/%@\\s*([^\\s<]+)/)?.[1] || '';
        out.push(item);
      }
      return { scope: 'results', papers: out };
    }

    // 详情页：单篇导出
    const exportUrl = document.querySelector('#export-url')?.value;
    const exportId = document.querySelector('#export-id')?.value;
    if (!exportUrl || !exportId) return { error: 'not_exportable_page' };

    const uniplatform = new URLSearchParams(location.search).get('uniplatform') || 'NZKPT';
    const resp = await fetch(exportUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        filename: exportId,
        displaymode: 'GBTREFER,elearning,EndNote',
        uniplatform
      })
    });
    const data = await resp.json();
    if (data.code !== 1) return { error: data.msg || 'export_failed' };
    const item = { n: 1, pageUrl: location.href };
    for (const entry of data.data) item[entry.mode] = entry.value[0];
    item.issn = document.body.innerText.match(/ISSN[：:]\\s*(\\S+)/)?.[1] || '';
    return { scope: 'detail', papers: [item] };
  })()`;

  const result = await evalJs(target, js);
  if (result?.error === "not_exportable_page") {
    fail(
      "当前页面没有导出入口",
      "请在 CNKI 检索结果页（可带 --indices 选篇），或论文详情页上运行。",
    );
  }

  const outPath = argText(args.out);
  if (outPath) {
    const abs = path.resolve(outPath);
    mkdirSync(path.dirname(abs), { recursive: true });
    // ENDNOTE 是 RIS-ish 的通用交换格式，Elearning 便于二次解析；gbt 只取引用串
    writeFileSync(abs, JSON.stringify(result.papers, null, 2));
    result.writtenTo = abs;
  }

  if (mode === "gbt") {
    result.citations = result.papers.map((p) => ({
      n: p.n,
      citation: p.GBTREFER || "",
      url: p.pageUrl,
    }));
  }

  emit(result);
}

const JOURNAL_JS = `(async () => {
  const items = Array.from(document.querySelectorAll('.result-table-list tbody tr, .knavi-list li, li.item'))
    .map(li => {
      const link = li.querySelector('a');
      return {
        name: li.querySelector('.journal-title, .tit, a')?.innerText?.trim() || '',
        url: link?.href || '',
        info: li.innerText?.replace(/\\s+/g, ' ').trim().slice(0, 300) || ''
      };
    })
    .filter(x => x.name || x.url);

  return {
    items,
    url: location.href,
    indexing: Array.from(document.querySelectorAll('.journal-head-tag, .tag, .b-db, span')).map(e => e.innerText?.trim()).filter(Boolean).slice(0, 20),
    bodyText: document.body.innerText.slice(0, 4000)
  };
})()`;

async function cmdJournal(args) {
  const name = argText(args.name) || args._.join(" ");
  if (!name) fail("缺少 --name", '例：node cnki.mjs journal --name "计算机学报"');

  await ensureProxy();
  const target = await ensureCnkiTab({ reusePrefix: URLS.journalSearch });
  await navigate(target, URLS.journalSearch);
  await guardCaptcha(target);

  const js = `(async () => {
    const query = ${JSON.stringify(name)};
    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        if (document.querySelector('input.researchbtn') || document.querySelector('input#txt_search')) resolve();
        else if (++n > 30) reject(new Error('期刊检索页未加载'));
        else setTimeout(tick, 500);
      };
      tick();
    });

    const input = document.querySelector('input#txt_search') || document.querySelector('input[type=text]');
    if (!input) return { error: 'no_search_input' };
    input.value = query;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    (document.querySelector('input.researchbtn') || document.querySelector('input[type=button]'))?.click();

    await new Promise(resolve => setTimeout(resolve, 2500));
    return { ok: true, url: location.href };
  })()`;

  const searched = await evalJs(target, js);
  if (searched?.error) fail(searched.error, "期刊检索页结构可能变了，改用 cnki-journal 的详情 URL。");

  await guardCaptcha(target);
  emit({ query: name, targetId: target, ...(await evalJs(target, JOURNAL_JS)) });
}

async function cmdToc(args) {
  const journal = argText(args.journal) || args._.join(" ");
  if (!journal) fail("缺少 --journal", '例：node cnki.mjs toc --journal "计算机学报" --year 2025 --issue 01');

  await ensureProxy();
  const target = await ensureCnkiTab({ anyCnki: true });

  const js = `(() => ({
    journal,
    url: location.href,
    issues: Array.from(document.querySelectorAll('a')).filter(a => /\\d{4}\\s*年\\s*\\d+\\s*期/.test(a.innerText || ''))
      .map(a => ({ label: a.innerText.trim(), url: a.href })).slice(0, 40),
    paperRows: Array.from(document.querySelectorAll('.result-table-list tbody tr, li.item'))
      .map(li => ({ text: li.innerText?.replace(/\\s+/g, ' ').trim().slice(0, 200) })).slice(0, 60)
  }))()`;

  emit({
    journal,
    year: argText(args.year) || "",
    issue: argText(args.issue) || "",
    note: "期刊目录需要先在 Chrome 里打开该刊的详情页；本命令只解析当前页面陈列的年份/期号与文章列表。",
    ...(await evalJs(target, js)),
  });
}

async function cmdDownload(args) {
  const url = argText(args.url);
  const format = (argText(args.format) || "pdf").toLowerCase();
  if (!["pdf", "caj"].includes(format)) fail(`不支持的 --format：${format}`, "可选：pdf / caj");

  await ensureProxy();
  const target = url
    ? await ensureCnkiTab({ reusePrefix: url })
    : await ensureCnkiTab({ anyCnki: true });
  if (url) await navigate(target, url);
  await guardCaptcha(target);

  const js = `(async () => {
    await new Promise((resolve, reject) => {
      let n = 0;
      const tick = () => {
        if (document.querySelector('.brief h1')) resolve();
        else if (++n > 30) reject(new Error('详情页未加载'));
        else setTimeout(tick, 500);
      };
      tick();
    });

    const cap = document.querySelector('#tcaptcha_transform_dy');
    if (cap && cap.getBoundingClientRect().top >= 0) return { error: 'captcha' };

    const notLogged = document.querySelector('.downloadlink.icon-notlogged')
      || document.querySelector('[class*="notlogged"]');
    if (notLogged) return { error: 'not_logged_in' };

    const format = ${JSON.stringify(format)};
    const pdfLink = document.querySelector('#pdfDown') || document.querySelector('.btn-dlpdf a');
    const cajLink = document.querySelector('#cajDown') || document.querySelector('.btn-dlcaj a');
    const title = document.querySelector('.brief h1')?.innerText?.trim()?.replace(/\\s*网络首发\\s*$/, '') || '';

    if (format === 'pdf' && pdfLink) { pdfLink.click(); return { status: 'downloading', format: 'PDF', title }; }
    if (format === 'caj' && cajLink) { cajLink.click(); return { status: 'downloading', format: 'CAJ', title }; }
    if (pdfLink) { pdfLink.click(); return { status: 'downloading', format: 'PDF', title }; }
    if (cajLink) { cajLink.click(); return { status: 'downloading', format: 'CAJ', title }; }
    return { error: 'no_download_link' };
  })()`;

  const result = await evalJs(target, js);
  if (result?.error === "not_logged_in") {
    fail("not_logged_in", "下载需要登录。请先在 Chrome 里登录知网账号，再重跑本命令。");
  }
  if (result?.error === "captcha") {
    fail("captcha", "CNKI 正在显示滑块验证码。请在 Chrome 里手动完成拼图验证，完成后告诉我继续。");
  }
  if (result?.error === "no_download_link") {
    fail("没找到下载链接", "该文献可能不提供 PDF/CAJ 下载（或需要机构权限）。");
  }

  emit({
    ...result,
    downloadDir: defaultDownloadDir(),
    hint: "文件会落到 Chrome 的下载目录。下载完成后跑 `cnki.mjs collect --title \"<标题>\" --into <目标目录>` 把它归档进语料库。",
  });
}

function defaultDownloadDir() {
  const home = os.homedir();
  const candidates =
    os.platform() === "darwin"
      ? [path.join(home, "Downloads")]
      : [path.join(home, "Downloads"), path.join(home, "下载")];
  return candidates.find((p) => existsSync(p)) || candidates[0];
}

/** 把 Chrome 刚下载的 PDF/CAJ 按标题归档进语料库目录。 */
async function cmdCollect(args) {
  const title = argText(args.title);
  const into = argText(args.into);
  if (!into) fail("缺少 --into", '例：cnki.mjs collect --title "论文标题" --into .pipeline/literature/<corpus>/papers');

  const dir = argText(args["download-dir"]) || defaultDownloadDir();
  const withinMinutes = Number(argText(args["within-minutes"]) || 30);
  const cutoff = Date.now() - withinMinutes * 60 * 1000;

  if (!existsSync(dir)) fail("下载目录不存在", `找不到 ${dir}，用 --download-dir 指定 Chrome 的下载目录。`);

  const candidates = readdirSync(dir)
    .filter((f) => /\.(pdf|caj)$/i.test(f))
    .map((f) => ({ file: path.join(dir, f), mtime: statSync(path.join(dir, f)).mtimeMs }))
    .filter((x) => x.mtime >= cutoff);

  if (title) {
    const slug = title.replace(/\s+/g, "");
    const matched = candidates.filter((x) => path.basename(x.file).replace(/\s+/g, "").includes(slug));
    if (matched.length) candidates.splice(0, candidates.length, ...matched);
  }

  if (!candidates.length) {
    fail(
      "没找到近期下载的文件",
      `${dir} 下 ${withinMinutes} 分钟内没有新的 PDF/CAJ。确认下载已完成，或用 --download-dir 指定别的目录。`,
    );
  }

  candidates.sort((a, b) => b.mtime - a.mtime);
  const picked = candidates[0].file;
  const destDir = path.resolve(into);
  mkdirSync(destDir, { recursive: true });
  const slug = (title || path.basename(picked, path.extname(picked)))
    .replace(/[\\/:*?"<>|]/g, "-")
    .slice(0, 80);
  const dest = path.join(destDir, slug, `paper${path.extname(picked)}`);
  mkdirSync(path.dirname(dest), { recursive: true });

  // 项目目录常在移动硬盘上，与下载目录不同卷，rename 会 EXDEV，退回复制 + 删除
  try {
    renameSync(picked, dest);
  } catch (error) {
    if (error.code !== "EXDEV") throw error;
    copyFileSync(picked, dest);
    unlinkSync(picked);
  }

  emit({ moved: dest, from: picked, candidates: candidates.length });
}

// ---------------------------------------------------------------- 入口

const COMMANDS = {
  status: cmdStatus,
  search: cmdSearch,
  advanced: cmdAdvanced,
  parse: cmdParse,
  pages: cmdPages,
  sort: cmdSort,
  detail: cmdDetail,
  export: cmdExport,
  journal: cmdJournal,
  toc: cmdToc,
  download: cmdDownload,
  collect: cmdCollect,
};

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  if (!command || command === "--help" || command === "-h") {
    emit({
      usage: "node cnki.mjs <command> [options]",
      commands: Object.keys(COMMANDS),
      note: "所有命令都需要 Chrome 开着远程调试并已登录知网；没有浏览器时返回 error 字段，退出码 2。",
    });
    return;
  }

  const handler = COMMANDS[command];
  if (!handler) fail(`未知子命令：${command}`, `可选：${Object.keys(COMMANDS).join(" ")}`);

  try {
    await handler(parseArgs(rest));
  } catch (error) {
    fail("runtime_error", `${error.message}`);
  }
}

main();
