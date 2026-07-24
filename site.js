const SITE = { headerSearchTimer: null, searchTimer: null };

function animeLink(a) {
  const nsfw = getNsfw() ? '&nsfw=1' : '';
  if (a.slug) return `/watch.html?slug=${encodeURIComponent(a.slug)}&ep=1${nsfw}`;
  if (a.id) return `/details.html?id=${a.id}${nsfw}`;
  return '#';
}
function animeHref(a) {
  const nsfw = getNsfw() ? '&nsfw=1' : '';
  if (a.id) return `/details.html?id=${a.id}${nsfw}`;
  if (a.slug) return `/details.html?slug=${encodeURIComponent(a.slug)}${nsfw}`;
  return '#';
}

function buildHeader() {
  const lang = getLang();
  const current = location.pathname.split('/').pop() || 'index.html';
  const navLinks = [
    { href: '/', label: t('Home'), key: 'index.html' },
    { href: '/browse', label: t('Browse'), key: 'browse.html' },
    { href: '/manga', label: t('Manga'), key: 'manga.html' },
    { href: '/schedule.html', label: t('Schedule'), key: 'schedule.html' },
    { href: '/top.html', label: t('Top Anime'), key: 'top.html' },
    { href: '/mylist.html', label: t('My List'), key: 'mylist.html' },
  ];
  document.getElementById('site-header').innerHTML = `
    <div class="brand" onclick="location.href='/'">夜想<span>YASŌ / NIGHT ARCHIVE</span></div>
    <nav><ul>
      ${navLinks.map(l => `<li><a href="${l.href}" class="${current===l.key?'active':''}">${l.label}</a></li>`).join('')}
      <li><div class="search-wrap"><span class="search-icon">⌕</span><input class="search-input" type="text" id="globalSearch" placeholder="${t('Search Anime...')}" autocomplete="off"><div class="search-dropdown" id="headerSuggestions"></div></div></li>
      <li><label class="nsfw-switch" title="18+ Content"><input type="checkbox" id="nsfwToggle" ${getNsfw() ? 'checked' : ''} onchange="toggleNsfw(this.checked)"><span class="nsfw-slider"></span><span class="nsfw-label">18+</span></label></li>
      <li><button class="lang-btn" onclick="toggleLang()">${lang==='en'?'日本語':'EN'}</button></li>
    </ul></nav>
    <button class="hamburger" id="hamburgerBtn" aria-label="Menu"><span class="hamburger-line"></span><span class="hamburger-line"></span><span class="hamburger-line"></span></button>
    <div class="mobile-backdrop" id="mobileBackdrop"></div>
    <div class="mobile-nav" id="mobileNav">
      ${navLinks.map(l => `<a href="${l.href}" class="${current===l.key?'active':''}">${l.label}</a>`).join('')}
      <a href="/search.html">${t('Search')}</a>
      <div class="mobile-nav-controls">
        <label class="nsfw-switch" title="18+ Content"><input type="checkbox" ${getNsfw() ? 'checked' : ''} onchange="toggleNsfw(this.checked)"><span class="nsfw-slider"></span><span class="nsfw-label">18+</span></label>
        <button class="lang-btn" onclick="toggleLang()">${lang==='en'?'日本語':'EN'}</button>
      </div>
    </div>`;
}

function toggleNsfw(checked) {
  setNsfw(checked);
  showToast(checked ? 'NSFW content enabled' : 'NSFW content disabled');
  setTimeout(() => location.reload(), 300);
}

function buildFooter() {
  const current = location.pathname.split('/').pop() || 'index.html';
  const footerImages = {
    'index.html': '/public/footer/footer-room.jpg',
    'browse.html': '/public/footer/footer-bw.jpg',
    'watch.html': '/public/footer/footer-dark.jpg',
    'details.html': '/public/footer/footer-moto.jpg',
    'schedule.html': '/public/footer/footer-ruins.jpg',
    'mylist.html': '/public/footer/footer-horns.jpg',
    'top.html': '/public/footer/footer-pink.jpg',
    'manga.html': '/public/footer/footer-dark.jpg',
    'manga-detail.html': '/public/footer/footer-moto.jpg',
  };
  const img = footerImages[current] || footerImages['index.html'];

  document.getElementById('site-footer').innerHTML = `
    <div class="foot-bg" style="background-image:url('${img}')"></div>
    <div class="foot-overlay"></div>
    <div class="foot-content">
      <div class="foot-brand">
        <div class="foot-seal">夜</div>
        <div class="foot-brand-text">
          <div class="foot-logo">夜想 YASŌ</div>
          <div class="foot-tagline">NIGHT ARCHIVE</div>
        </div>
      </div>
      <div class="foot-nav">
        <div class="foot-col">
          <div class="foot-col-title">${t('Navigate')}</div>
          <a href="/">${t('Home')}</a>
          <a href="/browse">${t('Browse')}</a>
          <a href="/manga">${t('Manga')}</a>
          <a href="/schedule.html">${t('Schedule')}</a>
        </div>
        <div class="foot-col">
          <div class="foot-col-title">${t('Discover')}</div>
          <a href="/top.html">${t('Top Anime')}</a>
          <a href="/mylist.html">${t('My List')}</a>
        </div>
      </div>
    </div>
    <div class="foot-bottom">
      <small>© YASŌ ARCHIVE — A NIGHT-SHIFT STREAMING STUDY</small>
      <small class="foot-shortcut-hint" onclick="showShortcuts()" style="cursor:pointer;opacity:0.75;transition:opacity 0.2s;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.75">Press <kbd style="background:var(--night-soft);padding:2px 6px;border-radius:3px;font-family:var(--font-m);font-size:.6rem;">?</kbd> for keyboard shortcuts</small>
    </div>`;
}

function initSearch() {
  const input = document.getElementById('globalSearch');
  if (!input) return;
  const box = document.getElementById('headerSuggestions');
  input.addEventListener('input', e => {
    clearTimeout(SITE.headerSearchTimer);
    const q = e.target.value.trim();
    if (q.length < 2) { box.classList.remove('active'); return; }
    SITE.headerSearchTimer = setTimeout(async () => {
      try {
        const results = await fetchSearch(q);
        if (!results.length) { box.classList.remove('active'); return; }
        box.innerHTML = results.slice(0, 8).map(r => {
          const href = animeHref(r);
          return `
          <div class="sg-item" onclick="location.href='${href}'">
            <img src="${r.cover||''}" alt="" onerror="this.style.display='none'">
            <div><div class="sg-item-title">${r.title||''}</div>
            <div class="sg-item-meta">${r.format||''} ${r.score?'★ '+r.score+'%':''}</div></div>
          </div>`;
        }).join('');
        box.classList.add('active');
      } catch(e) {}
    }, 300);
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const q = input.value.trim();
      if (q.length >= 2) { box.classList.remove('active'); location.href = '/search.html?q=' + encodeURIComponent(q); input.blur(); }
    }
  });
  document.addEventListener('click', e => { if (!e.target.closest('.search-wrap')) box.classList.remove('active'); });
}

function initPetals() {
  const host = document.getElementById('petals');
  if (!host) return;
  const count = window.innerWidth < 700 ? 12 : 22;
  for (let i = 0; i < count; i++) {
    const p = document.createElement('div');
    p.className = 'petal';
    p.style.left = Math.random() * 100 + '%';
    p.style.setProperty('--drift', (Math.random() * 120 - 60) + 'px');
    p.style.animationDuration = (8 + Math.random() * 10) + 's';
    p.style.animationDelay = (Math.random() * 10) + 's';
    p.style.opacity = (0.35 + Math.random() * 0.45).toFixed(2);
    host.appendChild(p);
  }
}

const revealObserver = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('in');
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

const cardObserver = new IntersectionObserver(entries => {
  entries.forEach((e, idx) => {
    if (e.isIntersecting) {
      setTimeout(() => e.target.classList.add('in'), (idx % 6) * 70);
      cardObserver.unobserve(e.target);
    }
  });
}, { threshold: 0.2 });

function observeReveals() {
  requestAnimationFrame(() => {
    document.querySelectorAll('.reveal, .brush').forEach((el, i) => {
      el.style.transitionDelay = (i % 4) * 80 + 'ms';
      revealObserver.observe(el);
    });
    document.querySelectorAll('.card').forEach(el => cardObserver.observe(el));
  });
}

function initHeroParallax() {
  const heroBg = document.querySelector('.hero-bg');
  const heroContent = document.querySelector('.hero-content');
  const scrollCue = document.querySelector('.scroll-cue');
  const hero = document.querySelector('.hero');
  if (!heroBg || !hero) return;
  const heroH = hero.offsetHeight;
  let raf = false;
  let lastY = 0;
  function update() {
    if (lastY < heroH) {
      const p = lastY / heroH;
      heroBg.style.transform = 'translateY(' + (lastY * 0.5) + 'px)';
      heroBg.style.opacity = 1 - p;
      if (heroContent) {
        heroContent.style.opacity = 1 - p * 2;
      }
      if (scrollCue) {
        scrollCue.style.opacity = Math.max(0, 1 - p * 3);
      }
    }
    raf = false;
  }
  window.addEventListener('scroll', function() {
    lastY = window.scrollY;
    if (!raf) { raf = true; requestAnimationFrame(update); }
  }, { passive: true });
}

function initLoader() {
  const loader = document.getElementById('loader');
  if (!loader) return;
  function hideLoader() {
    setTimeout(() => {
      loader.classList.add('done');
      setTimeout(() => loader.remove(), 700);
    }, 600);
  }
  if (document.readyState === 'complete') hideLoader();
  else window.addEventListener('load', hideLoader);
}

function renderCard(anime) {
  const title = anime.title || t('Untitled');
  const kj = title[0] || '?';
  const score = anime.score ? `★ ${anime.score}%` : '';
  const fmt = anime.format || '';
  const href = animeHref(anime);
  return `<div class="card" onclick="location.href='${href}'">
    <div class="card-content">
      <div class="card-front">
        <div class="card-art" style="background-image:url('${anime.cover||''}')">
          <div class="seal">印</div>
          <div class="kj">${kj}</div>
          <div class="ttl">${title}</div>
        </div>
        <div class="card-meta"><span>${fmt}</span><span>${score}</span></div>
      </div>
      <div class="card-back">
        <div class="card-back-glow"></div>
        <div class="card-back-inner">
          <div class="bcb-title">${title}</div>
          <div class="bcb-meta"><span>${fmt}</span><span>${score}</span></div>
          <div class="bcb-cta">${t('View Details')} →</div>
        </div>
      </div>
    </div>
  </div>`;
}

function renderBrowseCard(anime) {
  const title = anime.title || t('Untitled');
  const score = anime.score ? `★ ${anime.score}%` : '';
  const fmt = anime.format || '';
  const genres = (anime.genres || []).slice(0, 3);
  const href = animeHref(anime);
  return `<div class="bc" onclick="location.href='${href}'">
    <div class="bc-front">
      <img class="bc-art" src="${anime.cover||''}" alt="" onerror="handleImageError(this,'${(title||'').replace(/'/g,"\\'")}')">
      <div class="bc-gradient"></div>
      <div class="bc-score">${score}</div>
      <div class="bc-fmt">${fmt}</div>
      <div class="bc-title-overlay">${title}</div>
    </div>
    <div class="bc-back">
      <div class="bcb-title">${title}</div>
      <div class="bcb-meta"><span>${fmt}</span><span>${anime.episodes?anime.episodes+' '+t('ep'):''}</span><span>${score}</span></div>
      <div class="bcb-genres">${genres.map(g=>'<span>'+g+'</span>').join('')}</div>
      <div class="bcb-cta">${t('View Details')} →</div>
    </div>
  </div>`;
}

function renderAnikotoCard(a) {
  const slug = a.slug || '';
  const nsfw = getNsfw() ? '&nsfw=1' : '';
  const detailHref = `/details.html?slug=${encodeURIComponent(slug)}${nsfw}`;
  const watchHref = `/watch.html?slug=${encodeURIComponent(slug)}&ep=1${nsfw}`;
  const sub = a.sub || 0;
  const dub = a.dub || 0;
  let badges = '';
  if (sub) badges += `<span class="bc-ep-badge sub">${sub} SUB</span>`;
  if (dub) badges += `<span class="bc-ep-badge dub">${dub} DUB</span>`;
  return `<div class="bc" onclick="location.href='${detailHref}'">
    <div class="bc-front">
      <img class="bc-art" src="${a.cover || ''}" alt="" onerror="this.style.background='var(--night-soft)'">
      <div class="bc-gradient"></div>
      ${badges ? `<div class="bc-ep-badges">${badges}</div>` : ''}
      ${a.rating ? `<div class="bc-score">${a.rating}</div>` : ''}
      ${a.type ? `<div class="bc-fmt">${a.type}</div>` : ''}
      <div class="bc-title-overlay">${a.title || ''}</div>
    </div>
    <div class="bc-back">
      <div class="bcb-title">${a.title || ''}</div>
      <div class="bcb-meta">
        ${a.type ? `<span>${a.type}</span>` : ''}
        ${a.total_episodes ? `<span>${a.total_episodes} ${t('ep')}</span>` : ''}
        ${a.rating ? `<span>★ ${a.rating}</span>` : ''}
      </div>
      <div class="bcb-genres">${(a.genres || []).slice(0, 3).map(g => '<span>' + g + '</span>').join('')}</div>
      <div class="bcb-actions">
        <a class="bcb-btn bcb-btn-details" href="${detailHref}" onclick="event.stopPropagation()">${t('details →')}</a>
        <a class="bcb-btn bcb-btn-watch" href="${watchHref}" onclick="event.stopPropagation()">${t('Watch Now')} </a>
      </div>
    </div>
  </div>`;
}

function renderSpotlight(items) {
  if (!items || !items.length) return '';
  let html = '<div class="trend-grid">';
  items.slice(0, 8).forEach((a, i) => {
    const isLarge = i < 2;
    const href = animeHref(a);
    html += `<div class="tg-card${isLarge?' tg-large':''}" onclick="location.href='${href}'">
      <div class="tg-art" style="background-image:url('${(isLarge ? (a.banner||a.cover) : a.cover)||''}')"></div>
      <div class="tg-overlay"></div>
      <div class="tg-rank">${i+1}</div>
      <div class="tg-info">
        <div class="tg-title">${a.title||''}</div>
        <div class="tg-meta">${a.format||''} ${a.score?'★ '+a.score+'%':''} ${(a.genres||[]).slice(0,2).join(' · ')}</div>
      </div>
    </div>`;
  });
  html += '</div>';
  return html;
}

function renderPortraitRail(items) {
  return '<div class="portrait-rail">' + (items||[]).slice(0,12).map(a => {
    const ep = a.next_airing || a.episodes || '?';
    const href = animeHref(a);
    return `<div class="p-card" onclick="location.href='${href}'">
      <img class="p-art" src="${a.cover||''}" alt="" onerror="this.style.background='var(--night-soft)'">
      <div class="p-ep">${t('EP')} ${ep}</div>
      <div class="p-title">${a.title||''}</div>
      <div class="p-sub">${a.format||''} ${a.score?'★ '+a.score+'%':''}</div>
    </div>`;
  }).join('') + '</div>';
}

function renderDateList(items) {
  return '<div class="up-grid">' + (items||[]).slice(0,10).map(a => {
    const airDate = a.airing_at ? new Date(a.airing_at * 1000).toLocaleDateString('en-US', {month:'short',day:'numeric'}) : a.season||'';
    const href = animeHref(a);
    return `<div class="up-card" onclick="location.href='${href}'">
      <div class="up-art" style="background-image:url('${a.banner||a.cover||''}')"></div>
      <div class="up-overlay"></div>
      <div class="up-date">${airDate}</div>
      <div class="up-info">
        <div class="up-title">${a.title||''}</div>
        <div class="up-meta"><span>${a.format||''}</span><span>${a.episodes?a.episodes+' '+t('ep'):'?'}</span></div>
        <div class="up-genres">${(a.genres||[]).slice(0,3).map(g=>'<span>'+g+'</span>').join('')}</div>
      </div>
    </div>`;
  }).join('') + '</div>';
}

function renderBento(items) {
  if (!items || !items.length) return '';
  const main = items[0];
  const sm = items.slice(1, 5);
  const mainHref = animeHref(main);
  let html = '<div class="bento">';
  html += `<div class="bento-main" onclick="location.href='${mainHref}'">
    <div class="bn-art" style="background-image:url('${main.banner||main.cover||''}')"></div>
    <div class="bn-info"><div class="bn-title">${main.title||''}</div>
    <div class="bn-sub">${main.format||''} · ${main.score?'★ '+main.score+'%':''} · ${(main.genres||[]).slice(0,2).join(' · ')}</div></div>
  </div>`;
  sm.forEach(a => {
    const href = animeHref(a);
    html += `<div class="bento-sm" onclick="location.href='${href}'">
      <div class="bn-art" style="background-image:url('${a.cover||''}')"></div>
      <div class="bn-info"><div class="bn-title">${a.title||''}</div></div>
    </div>`;
  });
  html += '</div>';
  return html;
}

function renderCompactGrid(items) {
  return '<div class="compact-grid">' + (items||[]).slice(0,12).map(a => {
    const href = animeHref(a);
    return `<div class="c-card" onclick="location.href='${href}'">
      <img class="c-art" src="${a.cover||''}" alt="" onerror="this.style.background='var(--night-soft)'">
      <div class="c-title">${a.title||''}</div>
      <div class="c-meta">${a.format||''} ${a.score?'★ '+a.score+'%':''}</div>
    </div>`;
  }).join('') + '</div>';
}

function renderTimeline(items) {
  return '<div class="tl-rail">' + (items||[]).slice(0,10).map(a => {
    const href = animeHref(a);
    return `<div class="tl-hcard" onclick="location.href='${href}'">
      <div class="tlh-art" style="background-image:url('${a.banner||a.cover||''}')"></div>
      <div class="tlh-overlay"></div>
      <div class="tlh-badge">${t('COMPLETE')}</div>
      <div class="tlh-score">${a.score?'★ '+a.score+'%':''}</div>
      <div class="tlh-info">
        <div class="tlh-title">${a.title||''}</div>
        <div class="tlh-meta"><span>${a.format||''}</span><span>${a.episodes?a.episodes+' '+t('ep'):''}</span></div>
      </div>
    </div>`;
  }).join('') + '</div>';
}

function renderTopItem(anime, rank) {
  const title = anime.title || t('Untitled');
  const href = animeHref(anime);
  return `<div class="top-item" onclick="location.href='${href}'">
    <div class="top-rank">#${rank}</div>
    <img class="top-cover" src="${anime.cover||''}" alt="" onerror="this.style.background='var(--night-soft)'">
    <div class="top-info">
      <div class="top-title">${title}</div>
      <div class="top-meta">${anime.format||''} · ${anime.episodes?anime.episodes+' '+t('ep'):''} · ${anime.status||''}</div>
    </div>
    <div class="top-score">${anime.score?'★ '+anime.score+'%':''}</div>
  </div>`;
}

function initHamburger() {
  const btn = document.getElementById('hamburgerBtn');
  const nav = document.getElementById('mobileNav');
  const backdrop = document.getElementById('mobileBackdrop');
  if (!btn || !nav || !backdrop) return;
  function open() { btn.classList.add('open'); nav.classList.add('open'); backdrop.classList.add('open'); document.body.style.overflow = 'hidden'; }
  function close() { btn.classList.remove('open'); nav.classList.remove('open'); backdrop.classList.remove('open'); document.body.style.overflow = ''; }
  function toggle() { btn.classList.contains('open') ? close() : open(); }
  btn.addEventListener('click', toggle);
  backdrop.addEventListener('click', close);
  nav.querySelectorAll('a').forEach(a => a.addEventListener('click', close));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  let lastScroll = 0;
  window.addEventListener('scroll', () => {
    const hdr = document.getElementById('site-header');
    if (!hdr) return;
    window.scrollY > 50 ? hdr.classList.add('header-scrolled') : hdr.classList.remove('header-scrolled');
  }, { passive: true });
}

function initMobileCardFlip() {
  if (!matchMedia('(hover:none) and (pointer:coarse)').matches) return;
  document.querySelectorAll('.bc:not(.touch-bound),.card:not(.touch-bound)').forEach(el => {
    el.classList.add('touch-bound');
    el.addEventListener('touchstart', function(e) {
      if (e.target.closest('a,bcb-btn')) return;
      const wasFlipped = this.classList.contains('flipped');
      document.querySelectorAll('.bc.flipped,.card.flipped').forEach(c => c.classList.remove('flipped'));
      if (!wasFlipped) {
        e.preventDefault();
        this.classList.add('flipped');
      }
    }, { passive: false });
  });
}

function initSite() {
  buildHeader();
  buildFooter();
  initSearch();
  initHamburger();
  initPetals();
  initLoader();
  initHeroParallax();
  initMobileCardFlip();
  setTimeout(() => observeReveals(), 50);
  document.addEventListener('keydown', e => {
    if (e.key === '?' && !e.target.closest('input,textarea,select')) {
      e.preventDefault();
      showShortcuts();
    }
    if (e.key === 'Escape') {
      const o = document.getElementById('shortcutsOverlay');
      if (o) o.remove();
    }
  });
}

/* ── Continue Watching Rail ── */
function renderContinueWatching(items) {
  if (!items || !items.length) return '';
  return '<div class="cw-rail">' + items.slice(0, 12).map(a => {
    const pct = a.duration ? Math.round((a.time / a.duration) * 100) : 0;
    const mins = Math.floor((a.duration - a.time) / 60);
    const nsfw = getNsfw() ? '&nsfw=1' : '';
    const href = a.slug ? `/watch.html?slug=${encodeURIComponent(a.slug)}&ep=${a.ep}${nsfw}` : (a.id ? `/watch.html?id=${a.id}&ep=${a.ep}${nsfw}` : '#');
    return `<a class="cw-card" href="${href}">
      <div class="cw-cover-wrap">
        <img class="cw-cover" src="${a.cover||''}" alt="" onerror="this.style.background='var(--night-soft)'">
        <span class="cw-ep-badge">${t('EP')} ${a.ep}</span>
        <div class="cw-progress"><div class="cw-progress-bar" style="width:${pct}%"></div></div>
      </div>
      <div class="cw-info">
        <div class="cw-title">${a.title||''}</div>
        <div class="cw-meta">${mins > 0 ? mins + t('m left') : t('Almost done')}</div>
      </div>
    </a>`;
  }).join('') + '</div>';
}

/* ── My List Rail ── */
function renderMyList(items) {
  if (!items || !items.length) return '';
  return '<div class="wl-rail">' + items.slice(0, 12).map(a => {
    const nsfw = getNsfw() ? '&nsfw=1' : '';
    const href = a.slug ? `/details.html?slug=${encodeURIComponent(a.slug)}${nsfw}` : (a.id ? `/details.html?id=${a.id}${nsfw}` : '#');
    return `<a class="wl-card" href="${href}">
      <div class="wl-cover-wrap">
        <img class="wl-cover" src="${a.cover||''}" alt="" onerror="handleImageError(this,'${(a.title||'').replace(/'/g,"\\'")}')">
        <button class="wl-remove-btn" onclick="event.preventDefault();event.stopPropagation();removeFromWatchlist(${a.id});this.closest('.wl-card').remove();" title="${t('Remove')}">✕</button>
      </div>
      <div class="wl-info">
        <div class="wl-title">${a.title||''}</div>
        <div class="wl-meta">
          ${a.score ? `<span>★ ${a.score}%</span>` : ''}
          ${a.format ? `<span>${a.format}</span>` : ''}
        </div>
      </div>
    </a>`;
  }).join('') + '</div>';
}

function showShortcuts() {
  if (document.getElementById('shortcutsOverlay')) return;
  const overlay = document.createElement('div');
  overlay.id = 'shortcutsOverlay';
  overlay.className = 'shortcuts-overlay';
  overlay.innerHTML = `
    <div class="shortcuts-card">
      <div class="shortcuts-title">${t('Keyboard Shortcuts')}</div>
      <div class="shortcuts-grid">
        <div class="shortcut-row"><kbd>←</kbd><kbd>→</kbd><span>${t('Seek ±10s')}</span></div>
        <div class="shortcut-row"><kbd>↑</kbd><kbd>↓</kbd><span>${t('Volume ±10%')}</span></div>
        <div class="shortcut-row"><kbd>Space</kbd><span>${t('Play / Pause')}</span></div>
        <div class="shortcut-row"><kbd>F</kbd><span>${t('Fullscreen')}</span></div>
        <div class="shortcut-row"><kbd>M</kbd><span>${t('Mute')}</span></div>
        <div class="shortcut-row"><kbd>Esc</kbd><span>${t('Close overlay')}</span></div>
        <div class="shortcut-row"><kbd>?</kbd><span>${t('Show shortcuts')}</span></div>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}
