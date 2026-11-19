// Réceptionniste Telegram de Swamp Replay (Cloudflare Worker, offre gratuite).
// Telegram lui envoie chaque clic instantanément (webhook) :
//  - il répond tout de suite « ✅ Bien reçu » et remplace les 3 boutons par un bouton inactif (plus de double clic) ;
//  - il garde le clic (KV) jusqu'à ce que le robot GitHub le lise (GET /clics) puis le confirme (POST /ack).
// Un webhook actif empêche aussi tout autre programme de lire le bot (erreur 409 chez lui).
// Secrets du Worker : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEBHOOK_SECRET, ROBOT_KEY, YOUTUBE_STATE (posés par le workflow d'installation).
// YouTube (miniatures) : Google renvoie Chahine sur /youtube après son « Autoriser » ; le code est gardé ici (KV privée)
// jusqu'à ce que le robot l'échange, puis l'autorisation durable du robot est gardée ici aussi (jamais dans le dépôt public).

const LIBELLE = { v: "✅ Validé", r: "❌ Refusé", f: "🔁 Refaire demandé" };
const COMMANDES = { ok: "v", valider: "v", non: "r", refuser: "r" };

async function tg(env, methode, corps) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${methode}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(corps),
  });
  return r.json().catch(() => ({}));
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
}

async function recevoir(env, maj) {
  const cq = maj.callback_query;
  const msg = maj.message;
  const chat = String((cq ? cq.message?.chat?.id : msg?.chat?.id) ?? "");
  if (chat !== String(env.TELEGRAM_CHAT_ID)) return;                       // une autre personne : ignoré

  if (cq) {
    const [act, cle] = String(cq.data || "").split(":");
    if (!LIBELLE[act] || !cle) { await tg(env, "answerCallbackQuery", { callback_query_id: cq.id }); return; }
    const deja = await env.CLICS.get(`decision:${cle}`);
    if (deja) {                                                              // 2e clic : on ne change rien
      await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `Déjà enregistré : ${LIBELLE[deja]}`, show_alert: true });
      return;
    }
    await env.CLICS.put(`decision:${cle}`, act);
    await env.CLICS.put(`clic:${String(maj.update_id).padStart(12, "0")}`, JSON.stringify(maj));
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: `${LIBELLE[act]} — ${cle} bien reçu ✔️` });
    await tg(env, "editMessageReplyMarkup", {
      chat_id: cq.message.chat.id, message_id: cq.message.message_id,
      reply_markup: { inline_keyboard: [[{ text: `${LIBELLE[act]} — enregistré, le robot s'en occupe`, callback_data: "x:fait" }]] },
    });
    return;
  }

  const texte = String(msg?.text || "").trim();
  if (!texte.startsWith("/")) return;
  const [cmd, arg] = texte.slice(1).split(/\s+/);
  const act = COMMANDES[(cmd || "").split("@")[0].toLowerCase()];
  if (act && arg) {
    const cle = /^\d+$/.test(arg) ? "EP" + arg.padStart(3, "0") : arg.toUpperCase();
    const deja = await env.CLICS.get(`decision:${cle}`);
    if (deja) { await tg(env, "sendMessage", { chat_id: chat, text: `Déjà enregistré pour ${cle} : ${LIBELLE[deja]}` }); return; }
    await env.CLICS.put(`decision:${cle}`, act);
  }
  await env.CLICS.put(`clic:${String(maj.update_id).padStart(12, "0")}`, JSON.stringify(maj));
  await tg(env, "sendMessage", { chat_id: chat, text: act && arg ? `${LIBELLE[act]} — ${arg} bien reçu ✔️` : "Bien reçu ✔️ (le robot répond à son prochain passage)" });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === "/telegram" && req.method === "POST") {
      if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) return new Response("non", { status: 403 });
      try { await recevoir(env, await req.json()); } catch (e) { console.log("erreur", e); }
      return new Response("ok");                                             // toujours 200 : Telegram ne renvoie pas en boucle
    }
    if (url.pathname === "/youtube" && req.method === "GET") {              // retour de la page Google
      const page = (titre, texte) => new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">`
        + `<body style="font-family:sans-serif;background:#0b0e1f;color:#fff;text-align:center;padding:48px 16px">`
        + `<h1>${titre}</h1><p style="font-size:18px">${texte}</p></body>`, { headers: { "content-type": "text/html; charset=utf-8" } });
      const code = url.searchParams.get("code");
      if (!env.YOUTUBE_STATE || url.searchParams.get("state") !== env.YOUTUBE_STATE || !code)
        return page("❌ Autorisation non reçue", url.searchParams.get("error") ? "Google a répondu : " + url.searchParams.get("error") : "Lien invalide : reprends le bouton du bot Telegram.");
      await env.CLICS.put("youtube:code", code, { expirationTtl: 3600 });
      await tg(env, "sendMessage", { chat_id: env.TELEGRAM_CHAT_ID, text: "🔐 Autorisation YouTube reçue ✔️ Le robot la met en place à son prochain passage." });
      return page("✅ C'est fait", "Autorisation reçue. Tu peux fermer cette page : le robot confirmera sur Telegram.");
    }
    if (req.headers.get("X-Cle") !== env.ROBOT_KEY) return new Response("non", { status: 403 });
    if (url.pathname === "/youtube/jeton" && req.method === "GET")
      return json({ ok: true, code: await env.CLICS.get("youtube:code"), refresh: await env.CLICS.get("youtube:refresh") });
    if (url.pathname === "/youtube/jeton" && req.method === "POST") {
      const { refresh } = await req.json();
      if (refresh) await env.CLICS.put("youtube:refresh", refresh);
      return json({ ok: true });
    }
    if (url.pathname === "/youtube/code-lu" && req.method === "POST") { await env.CLICS.delete("youtube:code"); return json({ ok: true }); }
    if (url.pathname === "/youtube/oubli" && req.method === "POST") { await env.CLICS.delete("youtube:refresh"); return json({ ok: true }); }
    if (url.pathname === "/clics" && req.method === "GET") {
      const liste = await env.CLICS.list({ prefix: "clic:" });
      const maj = [];
      for (const k of liste.keys) { const v = await env.CLICS.get(k.name); if (v) maj.push(JSON.parse(v)); }
      return json({ ok: true, result: maj });
    }
    if (url.pathname === "/ack" && req.method === "POST") {
      const { ids = [] } = await req.json();
      for (const id of ids) await env.CLICS.delete(`clic:${String(id).padStart(12, "0")}`);
      return json({ ok: true, supprimes: ids.length });
    }
    return new Response("Réceptionniste Swamp Replay", { status: 200 });
  },
};
