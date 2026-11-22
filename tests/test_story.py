"""Story Instagram « NEW REEL » programmée 1 h après le Reel, si le PC a déposé {cle}_story.mp4."""
from datetime import datetime, timezone

from robot.etat import VALIDE
from robot.publieurs import Resultat
from test_youtube import monde  # noqa: F401


class FauxBuffer:
    def __init__(self): self.supprimes, self.crees = [], []
    def supprimer(self, pid): self.supprimes.append(pid)
    def programmer(self, pub): self.crees.append(pub); return Resultat(id_distant=f"n{len(self.crees)}", message="ok")
    def places_disponibles(self, p): return None


class FauxHeberg:
    def __init__(self, noms): self.noms = noms
    def lister(self): return [{"name": n, "browser_download_url": f"https://x/{n}"} for n in self.noms]
    def deposer(self, *a, **k): return {"url": "https://x/v.mp4"}


def preparer(o, t, noms):
    t[0] = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
    b = FauxBuffer()
    o._publieurs = {p: b for p in ("youtube", "tiktok", "instagram")}
    o._heberg = FauxHeberg(noms)
    o.etat.episodes.clear()
    o.etat.episodes["EP020"] = {"statut": VALIDE, "creneau": "2026-11-21T20:00:00+00:00", "meta": {"titre": "T", "hashtags": []},
                                "message_id": 1, "video_url": "https://x/EP020.mp4", "programme": {}}
    return b


def test_story_une_heure_apres_le_reel(monde):
    o, s, t = monde
    b = preparer(o, t, ["EP020.mp4", "EP020_story.mp4"])
    o.publier_valides()
    assert not [p for p in b.crees if p.story]                          # 10 h avant : trop tôt (file Buffer gratuite)
    t[0] = datetime(2026, 11, 21, 18, 0, tzinfo=timezone.utc)
    o.publier_valides()
    stories = [p for p in b.crees if p.story]
    assert len(stories) == 1 and stories[0].plateforme == "instagram"
    assert stories[0].date.isoformat() == "2026-11-21T21:00:00+00:00"
    assert stories[0].video_url == "https://x/EP020_story.mp4"
    assert o.etat.episodes["EP020"]["story"]["id"]
    o.publier_episode("EP020", o.etat.episodes["EP020"], dict(o.etat.episodes["EP020"]["meta"], id="EP020"))
    assert len([p for p in b.crees if p.story]) == 1                    # jamais deux fois


def test_pas_de_story_sans_video_story(monde):
    o, s, t = monde
    b = preparer(o, t, ["EP020.mp4"])
    o.publier_valides()
    assert not [p for p in b.crees if p.story] and "story" not in o.etat.episodes["EP020"]
