"""Miniature YouTube posée par le robot (Buffer ne sait pas le faire : il n'envoie que la vidéo).

Autorisation (une seule fois, demandée par le bot Telegram) :
  1. le robot envoie sur Telegram un bouton « 🔐 Autoriser YouTube » (page Google officielle) ;
  2. Chahine clique « Autoriser » ; Google renvoie vers le réceptionniste Cloudflare (/youtube), qui garde le code ;
  3. au passage suivant, le robot échange ce code contre une autorisation durable, gardée dans le réceptionniste
     (base KV privée) : jamais dans le dépôt public, jamais dans les journaux.
Ensuite, après chaque publication YouTube d'une vidéo validée ✅ sur Telegram, le robot retrouve le Short sur la chaîne
et y pose la miniature néon (EPxxx_couverture.jpg, celle envoyée avec la vidéo sur Telegram), puis prévient sur Telegram.

Secrets GitHub : YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET (client OAuth « Application Web » du projet Google Cloud).
Sans eux, cette étape ne fait rien.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests

from .etat import PROGRAMME, PUBLIE
from .reseau import ErreurHTTP, requete
from .telegram_bot import echapper

log = logging.getLogger(__name__)
PORTEES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
REDEMANDER = timedelta(hours=24)     # rappel du bouton d'autorisation tant qu'elle n'est pas donnée
ATTENTE_APRES_CRENEAU = timedelta(minutes=15)
ABANDON_APRES = timedelta(hours=36)  # Short introuvable sur la chaîne après ce délai : on prévient et on arrête
FENETRE = timedelta(days=9)          # les couvertures restent 10 jours dans la release


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "").casefold()
    return re.sub(r"\s+", " ", t).strip()


class MiniaturesYouTube:
    def __init__(self, orch):
        self.o = orch
        self.client_id = (os.environ.get("YOUTUBE_CLIENT_ID") or "").strip()
        self.client_secret = (os.environ.get("YOUTUBE_CLIENT_SECRET") or "").strip()
        self.session = orch.session or requests.Session()
        self._secrets = [self.client_secret]

    # ------------------------------------------------------------------ outils
    def masquer(self, texte: str) -> str:
        texte = self.o.secrets.masquer(texte)
        for v in self._secrets:
            if v and len(v) >= 6:
                texte = texte.replace(v, "***")
        return texte

    @property
    def tg(self) -> str:
        return self.o.secrets.telegram_token

    def etat(self) -> dict:
        return self.o.etat.donnees.setdefault("youtube", {})

    def relais(self) -> str | None:
        return self.o.adresse_relais()

    def cle_relais(self) -> dict:
        return {"X-Cle": hashlib.sha256(f"{self.tg}:robot".encode()).hexdigest()[:48]}

    def etat_oauth(self) -> str:
        return hashlib.sha256(f"{self.tg}:youtube".encode()).hexdigest()[:32]

    def lien_autorisation(self, relais: str) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": self.client_id, "redirect_uri": relais + "/youtube", "response_type": "code",
            "scope": PORTEES, "access_type": "offline", "prompt": "consent", "state": self.etat_oauth()})

    # ------------------------------------------------------------------ autorisation
    def coffre(self, relais: str) -> dict:
        return requete(self.session, "GET", relais + "/youtube/jeton", headers=self.cle_relais(),
                       etiquette="Réceptionniste YouTube").json()

    def ranger(self, relais: str, chemin: str, corps: dict | None = None) -> None:
        requete(self.session, "POST", relais + chemin, json=corps or {}, headers=self.cle_relais(),
                etiquette="Réceptionniste YouTube")

    def echanger(self, relais: str, code: str) -> str:
        r = requete(self.session, "POST", "https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": self.client_id, "client_secret": self.client_secret,
            "redirect_uri": relais + "/youtube", "grant_type": "authorization_code"},
            accepter=(400, 401), etiquette="Google (autorisation)")
        corps = r.json()
        if not corps.get("refresh_token"):
            raise RuntimeError(f"Google a refusé l'autorisation : {corps.get('error_description') or corps.get('error')}")
        self._secrets.append(corps["refresh_token"])
        return corps["refresh_token"]

    def acces(self, refresh: str) -> str | None:
        """Jeton d'accès d'une heure. None si l'autorisation a été retirée (il faudra la redemander)."""
        r = requete(self.session, "POST", "https://oauth2.googleapis.com/token", data={
            "refresh_token": refresh, "client_id": self.client_id, "client_secret": self.client_secret,
            "grant_type": "refresh_token"}, accepter=(400, 401), etiquette="Google (accès)")
        corps = r.json()
        if corps.get("error") == "invalid_grant":
            return None
        if not corps.get("access_token"):
            raise RuntimeError(f"Google : {corps.get('error_description') or corps.get('error')}")
        self._secrets.append(corps["access_token"])
        return corps["access_token"]

    def demander(self, relais: str) -> None:
        e = self.etat()
        der = e.get("demande_le")
        if der and self.o.maintenant() - datetime.fromisoformat(der) < REDEMANDER:
            return
        texte = ("🔐 <b>Autorisation YouTube</b>\n"
                 "Pour que le robot pose lui-même la miniature néon sur chaque Short validé ✅, il faut ton accord une seule fois.\n\n"
                 "1. Touche le bouton ci-dessous (page Google officielle), choisis le compte <b>swampreplay</b> / chaîne "
                 "<b>Swamp Replay</b>.\n2. Si Google affiche « appli non validée » : <i>Paramètres avancés</i> → <i>Accéder</i> "
                 "(normal, c'est ton robot à toi).\n3. Touche <b>Autoriser</b>.\n\nLe robot confirme ici au passage suivant.")
        self.o.bot.appel("sendMessage", json_corps={
            "chat_id": self.o.bot.chat_id, "text": texte, "parse_mode": "HTML", "disable_web_page_preview": True,
            "reply_markup": {"inline_keyboard": [[{"text": "🔐 Autoriser YouTube", "url": self.lien_autorisation(relais)}]]}})
        e["demande_le"] = self.o.maintenant().isoformat()

    def autorisation(self, relais: str) -> str | None:
        """Jeton d'accès prêt à servir, ou None (autorisation demandée sur Telegram)."""
        c = self.coffre(relais)
        refresh = c.get("refresh")
        if refresh:
            self._secrets.append(refresh)
        if not refresh and c.get("code"):
            self._secrets.append(c["code"])
            try:
                refresh = self.echanger(relais, c["code"])
            finally:
                self.ranger(relais, "/youtube/code-lu")                 # un code ne sert qu'une fois
            self.ranger(relais, "/youtube/jeton", {"refresh": refresh})
            self.etat().update(autorise_le=self.o.maintenant().isoformat(), demande_le=None)
            self.o.bot.envoyer_message("✅ <b>YouTube autorisé</b> : le robot posera la miniature néon sur chaque Short "
                                       "validé, après sa publication.")
        if not refresh:
            self.demander(relais)
            return None
        jeton = self.acces(refresh)
        if jeton is None:                                                # autorisation retirée côté Google
            self.ranger(relais, "/youtube/oubli")
            self.etat().update(autorise_le=None, demande_le=None)
            self.o.alerter("youtube-retire", "L'autorisation YouTube a été retirée : le robot la redemande.")
            self.demander(relais)
        return jeton

    # ------------------------------------------------------------------ miniatures
    def a_traiter(self) -> list[tuple[str, dict]]:
        maintenant = self.o.maintenant()
        sortie = []
        for cle, f in self.o.etat.episodes.items():
            if f.get("test") or f.get("miniature_yt") or f["statut"] not in (PROGRAMME, PUBLIE):
                continue
            if "youtube" not in (f.get("programme") or {}) or not f.get("creneau"):
                continue
            creneau = datetime.fromisoformat(f["creneau"])
            if creneau + ATTENTE_APRES_CRENEAU <= maintenant <= creneau + FENETRE:
                sortie.append((cle, f))
        return sortie

    def shorts_recents(self, jeton: str) -> dict[str, str]:
        h = {"Authorization": f"Bearer {jeton}"}
        ch = requete(self.session, "GET", "https://www.googleapis.com/youtube/v3/channels",
                     params={"part": "contentDetails", "mine": "true"}, headers=h, etiquette="YouTube chaîne").json()
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = requete(self.session, "GET", "https://www.googleapis.com/youtube/v3/playlistItems",
                     params={"part": "snippet", "playlistId": uploads, "maxResults": 50}, headers=h,
                     etiquette="YouTube vidéos").json()
        return {_norm(it["snippet"]["title"]): it["snippet"]["resourceId"]["videoId"] for it in pl.get("items", [])}

    def couverture(self, cle: str) -> bytes | None:
        h = self.o.conf["publication"]["hebergement"]
        depot = h.get("depot") or self.o.secrets.github_depot
        url = f"https://github.com/{depot}/releases/download/{h.get('tag_release', 'videos')}/{cle}_couverture.jpg"
        r = requete(self.session, "GET", url, accepter=(404,), etiquette="Couverture")
        return r.content if r.status_code == 200 and r.content else None

    def poser(self, jeton: str, video_id: str, image: bytes) -> None:
        requete(self.session, "POST", "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                params={"videoId": video_id, "uploadType": "media"}, data=image,
                headers={"Authorization": f"Bearer {jeton}", "Content-Type": "image/jpeg"}, etiquette="YouTube miniature")

    def cycle(self) -> None:
        if not (self.client_id and self.client_secret):
            return
        relais = self.relais()
        if not relais:
            log.warning("Miniatures YouTube : adresse du réceptionniste inconnue")
            return
        try:
            jeton = self.autorisation(relais)
            if not jeton:
                return
            liste = self.a_traiter()
            if not liste:
                return
            videos = self.shorts_recents(jeton)
            for cle, f in liste:
                titre = _norm(f.get("titre", ""))[:100]
                vid = videos.get(titre) or next((v for t, v in videos.items() if titre and (t.startswith(titre[:60]))), None)
                if not vid:
                    if self.o.maintenant() > datetime.fromisoformat(f["creneau"]) + ABANDON_APRES:
                        f["miniature_yt"] = "introuvable"
                        self.o.alerter(f"yt-{cle}", f"{cle} : Short introuvable sur la chaîne YouTube, miniature non posée.")
                    continue
                image = self.couverture(cle)
                if not image:
                    f["miniature_yt"] = "sans couverture"
                    continue
                self.poser(jeton, vid, image)
                f["miniature_yt"] = True
                f["youtube_id"] = vid
                log.info("Miniature YouTube posée : %s (%s)", cle, vid)
                self.o.bot.envoyer_message(f"🖼️ Miniature YouTube posée ✅ — <b>{echapper(cle)}</b>\n"
                                           f"https://youtube.com/shorts/{vid}")
        except ErreurHTTP as exc:
            raise RuntimeError(self.masquer(f"{exc} {getattr(exc, 'corps', '')[:300]}")) from None
