/*
 * Email Sorter core -- runs entirely in the browser (and in Node for tests).
 *
 * This is a JavaScript port of sort_emails.py + replies.py so the sorter can
 * run on a Chromebook (or any computer) with nothing installed. The rules
 * themselves are NOT duplicated here: build_web.py copies them out of
 * categories.py and replies.py when it builds "Email Sorter.html".
 */
(function (root) {
  'use strict';

  const LF = 0x0a;
  const CR = 0x0d;
  const MAX_PARSE_BYTES = 256 * 1024; // enough for headers + text; skips big attachments
  const BODY_CHARS = 3000;

  // ------------------------------------------------------------------------
  // Reading files: .mbox and Google Takeout .zip, streamed in chunks
  // ------------------------------------------------------------------------

  async function* streamChunks(readable, onBytes) {
    const reader = readable.getReader();
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) return;
        if (onBytes) onBytes(value.length);
        yield value;
      }
    } finally {
      reader.releaseLock();
    }
  }

  function isFromLine(buf, i, end) {
    return i + 5 <= end && buf[i] === 0x46 && buf[i + 1] === 0x72 && buf[i + 2] === 0x6f &&
      buf[i + 3] === 0x6d && buf[i + 4] === 0x20; // "From "
  }

  /*
   * Split a byte stream into raw mbox messages. A message starts at a
   * "From " line that follows a blank line (or starts the file).
   * Yielded arrays are only valid until the next iteration -- parse them
   * straight away.
   */
  async function* splitMbox(chunks) {
    let data = new Uint8Array(1 << 20);
    let len = 0;
    let start = 0; // start of the current message
    let scan = 0;  // next position to look for a newline

    for await (const chunk of chunks) {
      if (len + chunk.length > data.length) {
        if (start > 0) { // drop bytes of messages already handed out
          data.copyWithin(0, start, len);
          len -= start; scan -= start; start = 0;
        }
        if (len + chunk.length > data.length) {
          let cap = data.length;
          while (cap < len + chunk.length) cap *= 2;
          const bigger = new Uint8Array(cap);
          bigger.set(data.subarray(0, len));
          data = bigger;
        }
      }
      data.set(chunk, len);
      len += chunk.length;

      for (;;) {
        const nl = data.indexOf(LF, scan);
        if (nl === -1 || nl >= len) { scan = len; break; }
        if (nl + 6 > len) { scan = nl; break; } // need to see the next line's start
        const blankBefore = (nl - 1 >= start && data[nl - 1] === LF) ||
          (nl - 2 >= start && data[nl - 1] === CR && data[nl - 2] === LF);
        if (blankBefore && isFromLine(data, nl + 1, len) && nl + 1 > start) {
          yield data.subarray(start, nl + 1);
          start = nl + 1;
        }
        scan = nl + 1;
      }
    }
    if (len > start) yield data.subarray(start, len);
  }

  async function readSlice(file, start, end) {
    return new Uint8Array(await file.slice(start, end).arrayBuffer());
  }

  function u16(b, o) { return b[o] | (b[o + 1] << 8); }
  function u32(b, o) { return (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0; }
  function u64(b, o) { return u32(b, o) + u32(b, o + 4) * 4294967296; }

  function looksLikeZip(head) {
    return head.length >= 4 && head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04;
  }

  // List the entries of a zip file (supports Zip64 for exports over 4 GB).
  async function listZip(file) {
    const tailLen = Math.min(file.size, 65557);
    const tail = await readSlice(file, file.size - tailLen, file.size);
    let eocd = -1;
    for (let i = tail.length - 22; i >= 0; i--) {
      if (u32(tail, i) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('This zip file looks damaged. Try downloading it from Google again.');
    let count = u16(tail, eocd + 10);
    let cdSize = u32(tail, eocd + 12);
    let cdOffset = u32(tail, eocd + 16);
    const loc = eocd - 20;
    if (loc >= 0 && u32(tail, loc) === 0x07064b50) {
      const z64Off = u64(tail, loc + 8);
      const z64 = await readSlice(file, z64Off, z64Off + 56);
      if (u32(z64, 0) === 0x06064b50) {
        count = u64(z64, 32);
        cdSize = u64(z64, 40);
        cdOffset = u64(z64, 48);
      }
    }
    const cd = await readSlice(file, cdOffset, cdOffset + cdSize);
    const entries = [];
    const utf8 = new TextDecoder('utf-8');
    let p = 0;
    for (let n = 0; n < count && p + 46 <= cd.length; n++) {
      if (u32(cd, p) !== 0x02014b50) break;
      const method = u16(cd, p + 10);
      let compSize = u32(cd, p + 20);
      let size = u32(cd, p + 24);
      const nameLen = u16(cd, p + 28);
      const extraLen = u16(cd, p + 30);
      const commentLen = u16(cd, p + 32);
      let offset = u32(cd, p + 42);
      const name = utf8.decode(cd.subarray(p + 46, p + 46 + nameLen));
      let e = p + 46 + nameLen;
      const extraEnd = e + extraLen;
      while (e + 4 <= extraEnd) { // Zip64 extra field holds the real sizes
        const id = u16(cd, e);
        const sz = u16(cd, e + 2);
        if (id === 0x0001) {
          let q = e + 4;
          if (size === 0xffffffff) { size = u64(cd, q); q += 8; }
          if (compSize === 0xffffffff) { compSize = u64(cd, q); q += 8; }
          if (offset === 0xffffffff) { offset = u64(cd, q); q += 8; }
        }
        e += 4 + sz;
      }
      entries.push({ name, method, compSize, size, offset });
      p = extraEnd + commentLen;
    }
    return entries;
  }

  function countBytes(readable, onBytes) {
    if (!onBytes || typeof TransformStream === 'undefined') return readable;
    return readable.pipeThrough(new TransformStream({
      transform(chunk, controller) { onBytes(chunk.length); controller.enqueue(chunk); },
    }));
  }

  async function zipEntryStream(file, entry, onBytes) {
    const head = await readSlice(file, entry.offset, entry.offset + 30);
    if (u32(head, 0) !== 0x04034b50) throw new Error('This zip file looks damaged.');
    const dataStart = entry.offset + 30 + u16(head, 26) + u16(head, 28);
    const raw = countBytes(file.slice(dataStart, dataStart + entry.compSize).stream(), onBytes);
    if (entry.method === 0) return raw;
    if (entry.method !== 8) throw new Error('This zip file uses a format the sorter cannot read. Unzip it and choose the .mbox file inside.');
    if (typeof DecompressionStream === 'undefined') {
      throw new Error('This browser is too old to open zip files. Unzip the file first and choose the .mbox file inside.');
    }
    try {
      return raw.pipeThrough(new DecompressionStream('deflate-raw'));
    } catch (err) {
      throw new Error('This browser is too old to open zip files. Unzip the file first and choose the .mbox file inside.');
    }
  }

  /*
   * Yield [messageNumber, rawBytes] for every email in a Takeout .zip or an
   * .mbox file. onBytes(n) reports progress in bytes of the original file.
   */
  async function* iterMessages(file, onBytes) {
    const head = await readSlice(file, 0, 4);
    let n = 0;
    if (looksLikeZip(head)) {
      const members = (await listZip(file))
        .filter((e) => e.name.toLowerCase().endsWith('.mbox'))
        .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
      if (!members.length) {
        throw new Error('This zip file has no emails inside. If Google gave you more than one zip file, ' +
          'try the other one(s). Otherwise make sure the Takeout export included Mail.');
      }
      for (const entry of members) {
        const stream = await zipEntryStream(file, entry, onBytes);
        for await (const raw of splitMbox(streamChunks(stream))) {
          yield [++n, raw];
        }
      }
    } else {
      for await (const raw of splitMbox(streamChunks(file.stream(), onBytes))) {
        yield [++n, raw];
      }
    }
  }

  // ------------------------------------------------------------------------
  // Parsing one email
  // ------------------------------------------------------------------------

  function binStr(u8) {
    let s = '';
    for (let i = 0; i < u8.length; i += 8192) {
      s += String.fromCharCode.apply(null, u8.subarray(i, i + 8192));
    }
    return s;
  }

  function strBytes(s) {
    const out = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i) & 0xff;
    return out;
  }

  function decodeText(bytes, charset) {
    const label = (charset || 'utf-8').trim().replace(/^"|"$/g, '').toLowerCase();
    try {
      return new TextDecoder(label).decode(bytes);
    } catch (err) {
      return new TextDecoder('utf-8').decode(bytes);
    }
  }

  function b64Bytes(s) {
    let clean = s.replace(/[^A-Za-z0-9+/]/g, '');
    const rem = clean.length % 4; // restore padding so the last few bytes aren't lost
    if (rem === 1) clean = clean.slice(0, -1);
    else if (rem) clean += '='.repeat(4 - rem);
    try {
      return strBytes(atob(clean));
    } catch (err) {
      return new Uint8Array(0);
    }
  }

  function qpBinary(s) {
    return s.replace(/=\r?\n/g, '').replace(/=([0-9A-Fa-f]{2})/g, (m, h) => String.fromCharCode(parseInt(h, 16)));
  }

  // RFC 2047: =?utf-8?B?...?= and =?iso-8859-1?Q?...?= in headers
  function decodeWords(value) {
    if (value.indexOf('=?') === -1) return value;
    return value
      .replace(/(\?=)\s+(=\?)/g, '$1$2')
      .replace(/=\?([^?\s]+)\?([bBqQ])\?([^?\s]*)\?=/g, (m, charset, enc, text) => {
        const cs = charset.split('*')[0];
        const bytes = enc.toUpperCase() === 'B'
          ? b64Bytes(text)
          : strBytes(qpBinary(text.replace(/_/g, ' ')));
        return decodeText(bytes, cs);
      });
  }

  // Split a binary string entity into {headers, body}. Header names are lowercase.
  function parseEntity(s) {
    let end = -1;
    let bodyStart = s.length;
    for (let i = s.indexOf('\n'); i !== -1; i = s.indexOf('\n', i + 1)) {
      if (i === 0 || s[i + 1] === '\n') { end = i; bodyStart = i + 2; break; }
      if (s[i + 1] === '\r' && s[i + 2] === '\n') { end = i; bodyStart = i + 3; break; }
    }
    if (s[0] === '\n') { end = 0; bodyStart = 1; }
    const headText = decodeText(strBytes(end === -1 ? s : s.slice(0, end)), 'utf-8');
    const headers = {};
    const unfolded = headText.replace(/\r?\n[ \t]+/g, ' ').split(/\r?\n/);
    for (const line of unfolded) {
      const colon = line.indexOf(':');
      if (colon <= 0) continue;
      const name = line.slice(0, colon).trim().toLowerCase();
      if (!(name in headers)) headers[name] = line.slice(colon + 1).trim();
    }
    return { headers, body: end === -1 ? '' : s.slice(bodyStart) };
  }

  function headerParam(value, name) {
    const m = new RegExp(';\\s*' + name + '\\s*=\\s*(?:"([^"]*)"|([^;\\s]*))', 'i').exec(value || '');
    return m ? (m[1] !== undefined ? m[1] : m[2]) : '';
  }

  function splitMultipart(body, boundary) {
    const delim = '--' + boundary;
    const parts = [];
    let pos = body.startsWith(delim) ? 0 : body.indexOf('\n' + delim);
    if (pos === -1) return parts;
    if (pos > 0 || body[0] === '\n') pos += 1;
    for (;;) {
      if (body.startsWith(delim + '--', pos)) break;
      const lineEnd = body.indexOf('\n', pos);
      if (lineEnd === -1) break;
      const next = body.indexOf('\n' + delim, lineEnd);
      let part = body.slice(lineEnd + 1, next === -1 ? body.length : next);
      if (part.endsWith('\r')) part = part.slice(0, -1);
      parts.push(part);
      if (next === -1) break;
      pos = next + 1;
    }
    return parts;
  }

  function decodeBody(headers, body) {
    const cte = (headers['content-transfer-encoding'] || '').trim().toLowerCase();
    let bytes;
    if (cte === 'base64') bytes = b64Bytes(body.slice(0, 40000));
    else if (cte === 'quoted-printable') bytes = strBytes(qpBinary(body.slice(0, 40000)));
    else bytes = strBytes(body.slice(0, 40000));
    return decodeText(bytes, headerParam(headers['content-type'], 'charset'));
  }

  const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', '#39': "'" };
  function htmlToText(html) {
    return html
      .replace(/<(script|style)\b[\s\S]*?<\/\1\s*>/gi, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&(#x[0-9a-f]+|#\d+|[a-z]+\d*);/gi, (m, e) => {
        if (e[0] === '#') {
          const code = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
          try { return String.fromCodePoint(code); } catch (err) { return ' '; }
        }
        return ENTITIES[e.toLowerCase()] !== undefined ? ENTITIES[e.toLowerCase()] : m;
      });
  }

  function findText(entity, depth, found) {
    const ctypeHeader = entity.headers['content-type'] || 'text/plain';
    const ctype = ctypeHeader.split(';')[0].trim().toLowerCase();
    const disposition = (entity.headers['content-disposition'] || '').trim().toLowerCase();
    if (ctype.startsWith('multipart/')) {
      const boundary = headerParam(ctypeHeader, 'boundary');
      if (!boundary || depth > 6) return;
      for (const part of splitMultipart(entity.body, boundary)) {
        findText(parseEntity(part), depth + 1, found);
        if (found.plain !== null) return;
      }
      return;
    }
    if (disposition.startsWith('attachment')) return;
    if (ctype === 'text/plain' && found.plain === null) found.plain = decodeBody(entity.headers, entity.body);
    else if (ctype === 'text/html' && found.html === null) found.html = decodeBody(entity.headers, entity.body);
  }

  function parseAddr(value) {
    const v = (value || '').trim();
    let name = '';
    let addr = v;
    const lt = v.lastIndexOf('<');
    const gt = lt === -1 ? -1 : v.indexOf('>', lt);
    if (lt !== -1 && gt > lt) {
      name = v.slice(0, lt).trim();
      addr = v.slice(lt + 1, gt).trim();
    } else {
      const m = /^([^\s(]+)\s*\((.*)\)\s*$/.exec(v);
      if (m) { addr = m[1]; name = m[2]; }
    }
    name = name.replace(/^"([\s\S]*)"$/, '$1').replace(/\\(.)/g, '$1').trim();
    return { name, addr: addr.replace(/^mailto:/i, '').trim() };
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function formatDate(value) {
    if (!value) return '';
    const d = new Date(value.replace(/\s*\([^)]*\)\s*$/, ''));
    if (isNaN(d.getTime())) return '';
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' +
      pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function parse(raw) {
    let s = binStr(raw.subarray(0, MAX_PARSE_BYTES));
    if (s.startsWith('From ')) {
      const nl = s.indexOf('\n');
      s = nl === -1 ? '' : s.slice(nl + 1);
    }
    const entity = parseEntity(s);
    const h = entity.headers;
    const from = parseAddr(decodeWords(h.from || ''));
    const addr = from.addr.toLowerCase();
    let body = '';
    try {
      const found = { plain: null, html: null };
      findText(entity, 0, found);
      const text = found.plain !== null ? found.plain : htmlToText(found.html || '');
      body = text.replace(/\s+/g, ' ').trim().slice(0, BODY_CHARS);
    } catch (err) {
      body = '';
    }
    const precedence = (h.precedence || '').trim().toLowerCase();
    return {
      date: formatDate(h.date || ''),
      from_name: from.name,
      from_addr: addr,
      reply_to: parseAddr(decodeWords(h['reply-to'] || '')).addr.toLowerCase(),
      domain: addr.indexOf('@') !== -1 ? addr.slice(addr.lastIndexOf('@') + 1) : '',
      subject: decodeWords(h.subject || '').replace(/\s+/g, ' ').trim(),
      labels: decodeWords(h['x-gmail-labels'] || ''),
      bulk: Boolean(h['list-unsubscribe']) || ['bulk', 'list', 'junk'].indexOf(precedence) !== -1,
      body,
    };
  }

  // ------------------------------------------------------------------------
  // Classifying (same logic as sort_emails.classify)
  // ------------------------------------------------------------------------

  function escapeRx(s) { return s.replace(/[.*+?^${}()|[\]\\\/-]/g, '\\$&'); }
  function isAlnum(ch) { return /^[A-Za-z0-9]$/.test(ch || ''); }

  function compileKeyword(keyword) {
    const wildcard = keyword.endsWith('*');
    const kw = keyword.replace(/\*+$/, '');
    const prefix = isAlnum(kw[0]) ? '\\b' : '';
    const suffix = isAlnum(kw[kw.length - 1]) && !wildcard ? '\\b' : '';
    return new RegExp(prefix + escapeRx(kw) + suffix, 'i');
  }

  function createSorter(RULES) {
    const rules = RULES.keyword_order.map((cat) => {
      const levels = RULES.keywords[cat];
      const list = [];
      for (const weight of Object.keys(levels)) {
        for (const kw of levels[weight]) list.push([Number(weight), compileKeyword(kw)]);
      }
      return [cat, list];
    });
    const platformNameRx = new RegExp('\\b(?:' + RULES.platform_names.map(escapeRx).join('|') + ')\\b', 'i');
    const priority = new Set(RULES.priority_categories);
    const pageLimits = new Map(RULES.page_categories);
    const generic = new Set(RULES.generic_name_words);

    function domainIn(domain, domains) {
      return domains.some((d) => domain === d || domain.endsWith('.' + d));
    }

    function score(subject, body) {
      const scores = new Map();
      const add = (cat, n) => scores.set(cat, (scores.get(cat) || 0) + n);
      for (const [cat, list] of rules) {
        for (const [weight, rx] of list) {
          if (rx.test(subject)) add(cat, weight * 2);
          if (rx.test(body)) add(cat, weight);
        }
      }
      return { scores, add };
    }

    function classify(m) {
      const labels = m.labels.split(',').map((l) => l.trim().toLowerCase());
      const domain = m.domain;
      if (labels.indexOf('sent') !== -1) return ['Sent', 'high', "Gmail 'Sent' label"];

      const isPlatform = domainIn(domain, RULES.platform_domains);
      const claimsPlatform = platformNameRx.test(m.from_name);
      if (claimsPlatform && !isPlatform) {
        return ['Possible Scam', 'high', "sender name '" + m.from_name + "' but domain is " + (domain || 'unknown')];
      }
      if (labels.indexOf('spam') !== -1) return ['Possible Scam', 'high', 'Gmail marked it as spam'];
      if (isPlatform) return ['Social Media Notifications', 'high', 'from ' + domain];
      if (domainIn(domain, RULES.licensing_domains)) {
        return ['Video Licensing & Rights', 'high', 'from licensing company ' + domain];
      }

      const { scores, add } = score(m.subject, m.body);
      if (m.bulk) add('Newsletters & Promotions', 4);
      if (labels.indexOf('category promotions') !== -1 || labels.indexOf('category updates') !== -1) {
        add('Newsletters & Promotions', 3);
      }
      if (labels.indexOf('category social') !== -1) add('Social Media Notifications', 3);

      if (!scores.size) return ['Needs Review', 'low', 'no matching rules'];
      const ranked = Array.from(scores.entries()).sort((a, b) => b[1] - a[1]).slice(0, 2);
      const [best, top] = ranked[0];
      const runnerUp = ranked.length > 1 ? ranked[1][1] : 0;
      if (top < RULES.min_score) return ['Needs Review', 'low', 'weak match (' + best + ', score ' + top + ')'];
      const confidence = top >= 6 && top >= runnerUp * 2 ? 'high' : 'low';
      return [best, confidence, 'keyword score ' + top + (runnerUp ? ' (next: ' + ranked[1][0] + ' ' + runnerUp + ')' : '')];
    }

    // -- replies (same as replies.py) --------------------------------------
    function firstName(displayName) {
      const words = (displayName || '').replace(/"/g, '').match(/[A-Za-z'\-]+/g);
      if (!words || words.some((w) => generic.has(w.toLowerCase()))) return 'there';
      const word = words[0];
      if (/^[A-Za-z][A-Za-z'\-]{1,20}$/.test(word)) return word[0].toUpperCase() + word.slice(1).toLowerCase();
      return 'there';
    }

    function draftReply(category, displayName, signature) {
      const template = RULES.templates[category];
      if (!template) return '';
      return template.replace(/\{name\}/g, firstName(displayName)).replace(/\{signature\}/g, signature);
    }

    function replySubject(subject) {
      subject = subject || '';
      return /^re:/i.test(subject) ? subject : ('Re: ' + subject).trim();
    }

    function byDateDesc(a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : 0; }

    function collect(items) {
      const byCat = new Map(RULES.page_categories.map(([c]) => [c, []]));
      for (const it of items) if (byCat.has(it.category)) byCat.get(it.category).push(it);
      let chosen = [];
      for (const [cat, limit] of RULES.page_categories) {
        const rows = byCat.get(cat).slice().sort(byDateDesc);
        chosen = chosen.concat(limit ? rows.slice(0, limit) : rows);
      }
      return chosen;
    }

    function escHtml(s) {
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
    }

    function replyPageData(items, signature) {
      return collect(items).map((it) => ({
        id: it.id,
        category: it.category,
        date: it.date,
        from: it.from_name || it.from_addr,
        to: it.reply_to || it.from_addr,
        subject: it.subject,
        reply_subject: replySubject(it.subject),
        preview: it.snippet || '',
        draft: draftReply(it.category, it.from_name, signature),
      }));
    }

    function replyPageHtml(items, key, signature) {
      const data = JSON.stringify(replyPageData(items, signature)).replace(/<\//g, '<\\/');
      const tabs = RULES.page_categories
        .map(([c]) => '<button class="tab" data-cat="' + escHtml(c) + '">' + escHtml(c) + '</button>').join('');
      return RULES.reply_page
        .replace('{{TABS}}', () => tabs)
        .replace('{{KEY}}', () => JSON.stringify(key))
        .replace('{{DATA}}', () => data);
    }

    // -- the whole run -----------------------------------------------------
    const FIELDS = ['id', 'date', 'category', 'confidence', 'from_name', 'from_addr', 'subject', 'reason', 'preview'];

    function csvCell(v) {
      const s = String(v === undefined || v === null ? '' : v);
      return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    }
    function csvRow(row) { return FIELDS.map((f) => csvCell(row[f])).join(',') + '\r\n'; }

    /*
     * Sort every email in `file`. progress({emails, fraction}) is called now
     * and then. Returns counts, CSV text, and the reply page items.
     */
    async function run(file, progress) {
      const counts = new Map(RULES.categories.map((c) => [c, 0]));
      const allCsv = ['﻿' + FIELDS.join(',') + '\r\n'];
      const priorityRows = [];
      const replyItems = [];
      const capped = new Map(RULES.page_categories.filter(([, l]) => l).map(([c]) => [c, []]));
      let bytesDone = 0;
      let lastReport = 0;
      const onBytes = (n) => { bytesDone += n; };
      let n = 0;

      for await (const [id, raw] of iterMessages(file, onBytes)) {
        n = id;
        let m;
        let cat;
        let conf;
        let reason;
        try {
          m = parse(raw);
          [cat, conf, reason] = classify(m);
        } catch (err) {
          m = { date: '', from_name: '', from_addr: '', subject: '', body: '', reply_to: '' };
          [cat, conf, reason] = ['Needs Review', 'low', 'could not parse: ' + err.message];
        }
        const row = {
          id, date: m.date, category: cat, confidence: conf, from_name: m.from_name,
          from_addr: m.from_addr, subject: m.subject, reason, preview: m.body.slice(0, 200),
        };
        allCsv.push(csvRow(row));
        counts.set(cat, (counts.get(cat) || 0) + 1);
        if (priority.has(cat)) priorityRows.push(row);
        if (pageLimits.has(cat)) {
          const item = Object.assign({}, row, { reply_to: m.reply_to, snippet: m.body.slice(0, 600) });
          const limit = pageLimits.get(cat);
          if (!limit) {
            replyItems.push(item);
          } else {
            const list = capped.get(cat);
            list.push(item);
            if (list.length >= limit * 10) capped.set(cat, list.sort(byDateDesc).slice(0, limit));
          }
        }
        if (progress && id - lastReport >= 500) {
          lastReport = id;
          progress({ emails: id, fraction: file.size ? Math.min(1, bytesDone / file.size) : 0 });
          await new Promise((r) => setTimeout(r, 0)); // let the page repaint
        }
      }
      for (const list of capped.values()) for (const it of list) replyItems.push(it);
      priorityRows.sort(byDateDesc);
      const priorityCsv = ['﻿' + FIELDS.join(',') + '\r\n'].concat(priorityRows.map(csvRow));
      if (progress) progress({ emails: n, fraction: 1 });
      return { total: n, counts, allCsv, priorityCsv, replyItems };
    }

    return { parse, classify, firstName, draftReply, replySubject, collect, replyPageData, replyPageHtml, run };
  }

  // Short stable ID for a file, so saved reply-page ticks stay per inbox.
  function fileKey(name, size) {
    let h = 0x811c9dc5;
    const s = name + '|' + size;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return 'web' + h.toString(16);
  }

  const api = { createSorter, iterMessages, splitMbox, streamChunks, listZip, fileKey, parseAddr, decodeWords };
  root.EmailSorterCore = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
