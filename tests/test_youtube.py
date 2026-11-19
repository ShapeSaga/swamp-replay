"""Miniatures YouTube : autorisation demandée sur Telegram, code échangé, miniature posée après publication.
FAUX serveurs (Telegram, réceptionniste, Google, GitHub) : aucune vraie clé."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from robot import reseau
from robot.config import Secrets, charger_config
from robot.etat import PROGRAMME, Etat
from robot.orchestrateur import Orchestrateur
from robot.youtube import MiniaturesYouTube

reseau.dormir = lambda s: None
RELAIS = "https://relais.test"


class Rep:
    def __init__(self, donnees, statut=200, contenu=b""):
        self._d, self.status_code, self.headers = donnees, statut, {}
        self.text = json.dumps(donnees); self.ok = statut < 400; self.content = contenu

    def json(self):
        return self._d


class Faux:
    def __init__(self):
        self.headers = {}; self.kv = {}; self.messages = []; self.poses = []; self.revoque = False

    def request(self, methode, url, **kw):
        if "api.telegram.org" in url:
            self.messages.append(kw.get("json") or kw.get("data"))
            return Rep({"ok": True, "result": {"message_id": len(self.messages)}})
        if url.startswith(RELAIS):
            assert kw["headers"]["X-Cle"]
            chemin = url[len(RELAIS):]
            if chemin == "/youtube/jeton" and methode == "GET":
                return Rep({"ok": True, "code": self.kv.get("code"), "refresh": self.kv.get("refresh")})
            if chemin == "/youtube/jeton":
                self.kv["refresh"] = kw["json"]["refresh"]; return Rep({"ok": True})
            if chemin == "/youtube/code-lu":
                self.kv.pop("code", None); return Rep({"ok": True})
            if chemin == "/youtube/oubli":
                self.kv.pop("refresh", None); return Rep({"ok": True})
        if url == "https://oauth2.googleapis.com/token":
            d = kw["data"]
            if d["grant_type"] == "authorization_code":
                assert d["code"] == "CODE1" and d["redirect_uri"] == RELAIS + "/youtube"
                return Rep({"refresh_token": "RT-secret", "access_token": "AT1"})
            if self.revoque:
                return Rep({"error": "invalid_grant"}, 400)
            return Rep({"access_token": "AT2"})
        if "youtube/v3/channels" in url:
            return Rep({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        if "youtube/v3/playlistItems" in url:
            return Rep({"items": [{"snippet": {"title": "Pikachu vs Gengar… one hit could end it ⚡👻 #shorts",
                                               "resourceId": {"videoId": "VID42"}}}]})
        if "releases/download" in url:
            return Rep({}, 200, b"\xff\xd8jpeg")
        if "thumbnails/set" in url:
            assert kw["params"]["videoId"] == "VID42" and kw["data"].startswith(b"\xff\xd8")
            self.poses.append(kw["params"]["videoId"]); return Rep({"kind": "youtube#thumbnailSetResponse"})
        raise AssertionError(f"appel inattendu : {methode} {url}")


@pytest.fixture
def monde(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "GOCSPX-secret")
    monkeypatch.setattr(Orchestrateur, "adresse_relais", lambda self: RELAIS)
    s = Faux()
    t = [datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)]
    o = Orchestrateur(config=charger_config(), secrets=Secrets("tok", "42", "buf", "ghp", "ShapeSaga/swamp-replay"),
                      etat=Etat(tmp_path / "etat.json"), session=s, maintenant=lambda: t[0], dossier_episodes=tmp_path)
    o.etat.episodes["EP050"] = {"statut": PROGRAMME, "titre": "Pikachu vs Gengar… one hit could end it ⚡👻 #shorts",
                                "creneau": (t[0] - timedelta(minutes=30)).isoformat(), "programme": {"youtube": "p1"}}
    return o, s, t


def test_demande_puis_autorisation_puis_miniature(monde):
    o, s, t = monde
    MiniaturesYouTube(o).cycle()                                       # pas encore autorisé : bouton envoyé
    assert len(s.messages) == 1 and "accounts.google.com" in json.dumps(s.messages[0])
    MiniaturesYouTube(o).cycle()                                       # pas de 2e bouton dans les 24 h
    assert len(s.messages) == 1 and not s.poses
    s.kv["code"] = "CODE1"                                             # Chahine a cliqué « Autoriser »
    MiniaturesYouTube(o).cycle()
    assert s.kv == {"refresh": "RT-secret"} and s.poses == ["VID42"]
    assert o.etat.episodes["EP050"]["miniature_yt"] is True
    assert "RT-secret" not in json.dumps(o.etat.donnees)               # jamais dans l'état public
    MiniaturesYouTube(o).cycle()                                       # déjà fait : rien de plus
    assert s.poses == ["VID42"]


def test_autorisation_retiree_redemandee(monde):
    o, s, t = monde
    s.kv["refresh"] = "RT-secret"; s.revoque = True
    MiniaturesYouTube(o).cycle()
    assert "refresh" not in s.kv and not s.poses
    assert any("accounts.google.com" in json.dumps(m) for m in s.messages)


def test_sans_client_rien(monde, monkeypatch):
    o, s, t = monde
    monkeypatch.delenv("YOUTUBE_CLIENT_ID")
    MiniaturesYouTube(o).cycle()
    assert not s.messages and not s.poses
