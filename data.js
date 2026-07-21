const API = '';

const GENRES = [
  { id: 'action', name: { en: 'Action', ja: 'アクション' }, kj: '闘' },
  { id: 'romance', name: { en: 'Romance', ja: 'ロマンス' }, kj: '恋' },
  { id: 'fantasy', name: { en: 'Fantasy', ja: 'ファンタジー' }, kj: '夢' },
  { id: 'comedy', name: { en: 'Comedy', ja: 'コメディ' }, kj: '笑' },
  { id: 'drama', name: { en: 'Drama', ja: 'ドラマ' }, kj: '涙' },
  { id: 'scifi', name: { en: 'Sci-Fi', ja: '科幻' }, kj: '科幻' },
  { id: 'horror', name: { en: 'Horror', ja: 'ホラー' }, kj: '怖' },
  { id: 'mystery', name: { en: 'Mystery', ja: 'ミステリー' }, kj: '怪' },
  { id: 'slice', name: { en: 'Slice of Life', ja: '日常' }, kj: '日常' },
  { id: 'sports', name: { en: 'Sports', ja: 'スポーツ' }, kj: '運動' },
  { id: 'supernatural', name: { en: 'Supernatural', ja: '超自然' }, kj: '超' },
  { id: 'adventure', name: { en: 'Adventure', ja: '冒険' }, kj: '冒' },
  { id: 'psychological', name: { en: 'Psychological', ja: '心理' }, kj: '心理' },
  { id: 'music', name: { en: 'Music', ja: '音楽' }, kj: '音' },
];

const JP_WORDS = {
  'Home': 'ホーム', 'Browse': '一覧', 'Search': '検索', 'Top Anime': 'トップアニメ',
  'Trending': 'トレンド', 'Recent': '最近', 'New Releases': '新作', 'Popular': '人気',
  'Movies': '映画', 'OVAs': 'OVA', 'ONAs': 'ONA', 'TV Series': 'TVシリーズ',
  'Schedule': 'スケジュール', 'Genres': 'ジャンル', 'Studios': 'スタジオ', 'Season': 'シーズン',
  'Now Streaming': '今宵の配信', 'Top Ranked': 'トップランキング', 'Airing Schedule': '放送スケジュール',
  'Browse by Feeling': '感情で選ぶ', 'Explore All Anime': '全アニメを探す', 'Search Anime...': 'アニメを検索...',
  'Latest Episodes': '最新エピソード', 'Upcoming Anime': '近日公開',
  'New Added': '新規追加', 'Just Completed': '完結',
  'Episode': 'エピソード', 'Episodes': 'エピソード', 'Watch Now': '今見る', 'Add to List': 'リストに追加',
  'Score': 'スコア', 'Status': 'ステータス', 'Type': 'タイプ', 'Studio': 'スタジオ',
  'Airing': '放送中', 'Completed': '完結', 'Upcoming': '今後',
  'Monday': '月曜日', 'Tuesday': '火曜日', 'Wednesday': '水曜日', 'Thursday': '木曜日',
  'Friday': '金曜日', 'Saturday': '土曜日', 'Sunday': '日曜日',
  'Filter': 'フィルター', 'Sort': '並べ替え', 'Reset': 'リセット', 'All': 'すべて',
  'Japanese': '日本語', 'English': '英語', 'Rank': '順位', 'View Details': '詳細を見る',
  'Night Archive': '夜想アーカイブ', 'My List': 'マイリスト',
  'Continue Watching': '続きから', 'Pick Up Where You Left Off': '中断したところから再開',
  'Tonight\'s Selection': '今宵の選りすぐり',
  'Just Aired': '直近の放送', 'Coming Soon': '近日公開',
  'Fresh This Season': '今季の新作', 'Recently Added': '最近追加',
  'Finished': '完結済み', 'Choose By Emotion': '感情で選ぶ',
  'Stay Up One More Episode': 'もう1エピソード見てみよう',
  'New reels are stamped into the archive every night at 24:00.': '新作は毎晩24時にアーカイブに追加されます。',
  'Enter the Archive': 'アーカイブに入る', 'SCROLL': 'スクロール',
  'All Anime': '全アニメ', 'All Genres': '全ジャンル', 'All Types': '全タイプ',
  'anime found': '件のアニメが見つかりました', 'No anime found': 'アニメが見つかりませんでした',
  'Loading...': '読み込み中...', 'Failed to load': '読み込みに失敗しました',
  '← Prev': '← 前へ', 'Next →': '次へ →', 'Page': 'ページ',
  'Home': 'ホーム', 'Finding stream...': 'ストリームを検索中...',
  'Trending': 'トレンド', 'SUB': '字幕', 'DUB': '吹替', 'SERVER': 'サーバー',
  'Prev': '前', 'Next': '次', 'Ep': '第',
  'Auto-next episode': '自動で次のエピソード再生',
  'AUTO': '自動', 'Keyboard shortcuts': 'キーボードショートカット',
  'EPISODES': 'エピソード', 'Related': '関連作品',
  'More Like This': 'おすすめ', 'You Might Also Like': 'おすすめアニメ',
  'No trending data': 'トレンドデータなし',
  'NEXT EPISODE': '次のエピソード', 'Cancel': 'キャンセル',
  'Resume from ': '再開: ',
  'Skip Intro': 'イントロをスキップ', 'Skip Outro': 'アウトロをスキップ',
  'Keyboard Shortcuts': 'キーボードショートカット',
  'Previous episode': '前のエピソード', 'Next episode': '次のエピソード',
  'Play / Pause': '再生 / 一時停止', 'Fullscreen': 'フルスクリーン',
  'Cycle servers': 'サーバー切替', 'Cancel auto-next': '自動再生キャンセル',
  'Toggle this panel': 'パネル切替',
  'Synopse': 'あらすじ', 'Synopsis': 'あらすじ', 'Information': '情報',
  'Source': '原作', 'Duration': '尺', 'min': '分', 'Country': '国',
  'Relations': '関連作品', 'Staff': 'スタッフ', 'Rankings': 'ランキング',
  'Trailer': '予告編', 'Next Episode': '次回エピソード', 'Alt Titles': '別タイトル',
  '▶ Watch': '▶ 見る', 'In My List': 'リスト入り',
  'Weekly Airing Schedule': '週間放送スケジュール', 'Airing This Week': '今週の放送',
  'Airing now': '放送中', 'shows': '作品', 'No shows scheduled': '予定なし',
  'Failed to load schedule': 'スケジュールの読み込みに失敗しました',
  'Failed to load anime details': 'アニメ情報の読み込みに失敗しました',
  'Anime not found': 'アニメが見つかりません', 'No ID or slug provided': 'IDまたはスラッグが指定されていません',
  'Stream not found. ': 'ストリームが見つかりません。 ',
  'Untitled': '無題', 'details →': '詳細 →', 'ep': '話',
  'COMPLETE': '完結', 'EP': '第',
  'm left': '分残り', 'Almost done': 'もうすぐ終了',
  'Remove': '削除', 'TODAY': '今日',
  'Your list is empty': 'リストは空です',
  'Browse anime and click "Add to List" to save your favorites here.': 'アニメを探して「リストに追加」をクリックするとお気に入りが保存されます。',
  'Browse Anime': 'アニメを探す', 'Remove from list': 'リストから削除',
  '18+': '18+', 'Prev': '前',
  'on': 'に', 'shows this week': '今週の作品',
  'Avg': '平均', 'Next': '次',
  'Manga': '漫画', 'Read Now': '読む', 'Chapters': '話',
  'Chapter': '話', 'Continue Reading': '続きから',
  'Scroll Mode': 'スクロール', 'Page Mode': 'ページモード',
  'Pages': 'ページ', 'Read': '読了', 'Unread': '未読',
  'Browse Manga': '漫画を探す', 'Manga Detail': '漫画詳細',
  'All Manga': '全漫画', 'Manhwa': '漫画', 'Manhua': '漫画',
  'manga found': '件の漫画が見つかりました', 'No manga found': '漫画が見つかりませんでした',
  'Navigate': 'ナビゲート', 'Discover': '発見',
};

function t(en) {
  const lang = localStorage.getItem('yas_lang') || 'en';
  if (lang === 'ja') return JP_WORDS[en] || en;
  return en;
}

function getLang() { return localStorage.getItem('yas_lang') || 'en'; }
function setLang(lang) { localStorage.setItem('yas_lang', lang); location.reload(); }
function toggleLang() { setLang(getLang() === 'en' ? 'ja' : 'en'); }

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
  document.querySelectorAll('[data-i18n-sub]').forEach(el => {
    const parts = el.getAttribute('data-i18n-sub').split('|||');
    const jp = parts[0] || '';
    const enKey = parts[1] || '';
    el.textContent = jp + ' — ' + t(enKey);
  });
}

function getNsfw() { return localStorage.getItem('yas_nsfw') === 'true'; }
function setNsfw(val) { localStorage.setItem('yas_nsfw', val); }

async function api(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function fetchTrending() {
  if (getNsfw()) { const data = await api('/api/nsfw/trending'); return data.results || []; }
  const data = await api('/api/anikoto/trending');
  return data.results || [];
}

async function fetchBrowse(section) {
  if (getNsfw()) {
    let url = '/api/nsfw/homepage';
    const data = await api(url);
    const section_order = ["trending", "recent", "upcoming", "new_release", "new_added", "completed"];
    const sections = {};
    for (const k of section_order) sections[k] = data[k] || [];
    return { results: (section && sections[section]) || data.recent || [], total: 24, sections: section_order };
  }
  let url = '/api/browse';
  const params = [];
  if (section) params.push('section=' + encodeURIComponent(section));
  url += '?' + params.join('&');
  const data = await api(url);
  return data;
}

async function fetchBrowseCategory(category, page) {
  return api('/api/browse/' + encodeURIComponent(category) + '?page=' + (page || 1));
}

async function fetchBrowseGenre(slug, page) {
  if (getNsfw()) return api('/api/nsfw/homepage');
  return api('/api/browse/genre/' + encodeURIComponent(slug) + '?page=' + (page || 1));
}

async function fetchBrowseType(slug, page) {
  if (getNsfw()) return api('/api/nsfw/homepage');
  return api('/api/browse/type/' + encodeURIComponent(slug) + '?page=' + (page || 1));
}

async function fetchBrowseFilter(genre, termType, page) {
  if (getNsfw()) {
    if (genre) return api('/api/nsfw/search?q=' + encodeURIComponent(genre));
    return api('/api/nsfw/homepage');
  }
  let url = '/api/browse/filter?page=' + (page || 1);
  if (genre) url += '&genre=' + encodeURIComponent(genre);
  if (termType) url += '&term_type=' + encodeURIComponent(termType);
  return api(url);
}

async function fetchBrowseGenres() { return api('/api/browse/genres'); }
async function fetchBrowseTypes() { return api('/api/browse/types'); }

async function fetchSearch(q, page) {
  if (getNsfw()) {
    const data = await api('/api/nsfw/search?q=' + encodeURIComponent(q) + '&page=' + (page || 1));
    return data.results || [];
  }
  const data = await api('/search?q=' + encodeURIComponent(q) + '&page=' + (page || 1));
  return data.results || [];
}

async function fetchAnimeDetail(id) {
  const data = await api('/anime/' + id);
  return data.anime || data;
}

async function fetchAnilistSearch(q) {
  const data = await api('/api/anilist/search?q=' + encodeURIComponent(q));
  return data.results || [];
}

async function fetchStream(title, episode, source, slug) {
  return apiPost('/stream', { title, episode: Number(episode), source: source || 'auto', slug: slug || '' });
}

async function fetchAnikotoHomepage() {
  if (getNsfw()) return api('/api/nsfw/homepage');
  return api('/api/anikoto/homepage');
}
async function fetchAnikotoRecent() {
  if (getNsfw()) return api('/api/nsfw/recent');
  return api('/api/anikoto/recent');
}
async function fetchAnikotoUpcoming() {
  if (getNsfw()) return { results: [] };
  return api('/api/anikoto/upcoming');
}
async function fetchAnikotoNewRelease() {
  if (getNsfw()) return api('/api/nsfw/new-release');
  return api('/api/anikoto/new-release');
}
async function fetchAnikotoNewAdded() {
  if (getNsfw()) return api('/api/nsfw/new-added');
  return api('/api/anikoto/new-added');
}
async function fetchAnikotoCompleted() {
  if (getNsfw()) return api('/api/nsfw/completed');
  return api('/api/anikoto/completed');
}
async function fetchAnikotoTop() {
  if (getNsfw()) return api('/api/nsfw/top');
  return api('/api/anikoto/top');
}

async function fetchNsfwDetail(slug) { return api('/api/nsfw/detail?slug=' + encodeURIComponent(slug)); }
async function fetchNsfwStream(slug, episode) { return apiPost('/api/nsfw/stream', { slug: slug || '', episode: Number(episode || 1) }); }

async function fetchLatestEpisodes(page) { return api('/api/latest-episodes?page=' + (page||1)); }
async function fetchSchedule() { return api('/api/schedule'); }
async function fetchRecommendations(animeId) { return api('/api/anilist/recommendations/' + animeId); }
async function fetchSimilar(genre, exclude) { return api('/api/similar?genre=' + encodeURIComponent(genre || '') + '&exclude=' + encodeURIComponent(exclude || '')); }
async function fetchUpcoming(page) { return api('/api/upcoming?page=' + (page||1)); }
async function fetchNewReleases(page) { return api('/api/new-releases?page=' + (page||1)); }
async function fetchNewAdded(page) { return api('/api/new-added?page=' + (page||1)); }
async function fetchJustCompleted(page) { return api('/api/just-completed?page=' + (page||1)); }

/* ── Manga API ── */
async function fetchMangaSearch(q, page, origLang) {
  let url = '/api/manga/search?page=' + (page||1);
  if (q) url += '&q=' + encodeURIComponent(q);
  if (origLang) url += '&orig_lang=' + origLang;
  return api(url);
}
async function fetchMangaDetail(id) { return api('/api/manga/' + id); }
async function fetchMangaChapters(id, lang, page) {
  return api('/api/manga/' + id + '/chapters?lang=' + (lang||'en') + '&page=' + (page||1));
}
async function fetchMangaChapterImages(chapterId) { return api('/api/manga/chapter/' + chapterId); }

function getGenreById(id) { return GENRES.find(g => g.id === id); }

/* ── Watchlist (My List) ── */
function getWatchlist() {
  try { return JSON.parse(localStorage.getItem('kaa_watchlist')) || []; } catch(e) { return []; }
}
function addToWatchlist(anime) {
  const list = getWatchlist();
  if (list.some(a => a.id === anime.id)) return;
  list.unshift({ id: anime.id, slug: anime.slug || '', title: anime.title || '', cover: anime.cover || '', format: anime.format || '', score: anime.score || null, addedAt: Date.now() });
  if (list.length > 20) list.length = 20;
  localStorage.setItem('kaa_watchlist', JSON.stringify(list));
}
function removeFromWatchlist(id) {
  const list = getWatchlist().filter(a => a.id !== id);
  localStorage.setItem('kaa_watchlist', JSON.stringify(list));
}
function isInWatchlist(id) {
  return getWatchlist().some(a => a.id === id);
}
function toggleWatchlist(anime) {
  if (isInWatchlist(anime.id)) { removeFromWatchlist(anime.id); return false; }
  addToWatchlist(anime); return true;
}

/* ── Continue Watching ── */
function getContinueWatching() {
  try { return JSON.parse(localStorage.getItem('kaa_continue')) || []; } catch(e) { return []; }
}
function saveContinueWatching(entry) {
  let list = getContinueWatching().filter(e => !(e.slug === entry.slug && e.id === entry.id));
  list.unshift(entry);
  if (list.length > 20) list.length = 20;
  localStorage.setItem('kaa_continue', JSON.stringify(list));
}
function removeContinueWatching(slug, id) {
  const list = getContinueWatching().filter(e => !(e.slug === slug && e.id === id));
  localStorage.setItem('kaa_continue', JSON.stringify(list));
}
