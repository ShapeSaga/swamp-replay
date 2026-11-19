"""Récupération des vidéos déposées par le PC (release « videos »)."""
import json

from robot.etat import Etat
from robot.recuperer import recuperer


class FauxHebergeur:
    def __init__(self, fichiers: dict):
        self.fichiers = fichiers                      # nom -> contenu (bytes)
        self.telecharges = []

    def lister(self):
        return [{"id": i, "name": n, "size": len(c)} for i, (n, c) in enumerate(self.fichiers.items())]

    def telecharger(self, asset_id, destination):
        nom = list(self.fichiers)[asset_id]
        self.telecharges.append(nom)
        destination.write_bytes(self.fichiers[nom])
        return destination


def fiche(test=False):
    return json.dumps({"titre": "A vs B", "legende": "x", "hashtags": [], "test": test}).encode()


def test_prend_seulement_les_places_libres(tmp_path):
    h = FauxHebergeur({"EP001.mp4": b"v1", "EP001.json": fiche(), "EP001.jpg": b"j",
                       "EP002.mp4": b"v2", "EP002.json": fiche(),
                       "EP003.mp4": b"v3", "EP003.json": fiche()})
    pris = recuperer(h, Etat(tmp_path / "e.json"), places_vraies=2, places_test=0, dossier=tmp_path / "ep")
    assert pris == ["EP001", "EP002"]
    assert (tmp_path / "ep" / "EP001.mp4").read_bytes() == b"v1"
    assert (tmp_path / "ep" / "EP001.jpg").exists()
    assert "EP003.mp4" not in h.telecharges           # la réserve n'est pas téléchargée


def test_aucune_place_aucun_telechargement(tmp_path):
    h = FauxHebergeur({"EP001.mp4": b"v1", "EP001.json": fiche()})
    assert recuperer(h, Etat(tmp_path / "e.json"), 0, 0, dossier=tmp_path / "ep") == []
    assert h.telecharges == []


def test_ignore_episodes_connus_et_incomplets(tmp_path):
    etat = Etat(tmp_path / "e.json")
    etat.episodes["EP001"] = {"statut": "publie"}
    h = FauxHebergeur({"EP001.mp4": b"v1", "EP001.json": fiche(),
                       "EP002.json": fiche(),                     # vidéo pas encore déposée
                       "EP003.mp4": b"v3", "EP003.json": fiche()})
    assert recuperer(h, etat, 5, 0, dossier=tmp_path / "ep") == ["EP003"]


def test_episode_de_test_compte_sur_les_places_de_test(tmp_path):
    h = FauxHebergeur({"EP001.mp4": b"v1", "EP001.json": fiche(test=True),
                       "EP002.mp4": b"v2", "EP002.json": fiche()})
    pris = recuperer(h, Etat(tmp_path / "e.json"), places_vraies=0, places_test=1, dossier=tmp_path / "ep")
    assert pris == ["EP001"]
    assert not (tmp_path / "ep" / "EP002.json").exists()
    assert not list((tmp_path / "ep").glob("*.part"))


def test_deja_present_occupe_une_place(tmp_path):
    d = tmp_path / "ep"; d.mkdir()
    (d / "EP001.json").write_bytes(fiche()); (d / "EP001.mp4").write_bytes(b"v1")
    h = FauxHebergeur({"EP001.mp4": b"v1", "EP001.json": fiche(), "EP002.mp4": b"v2", "EP002.json": fiche()})
    assert recuperer(h, Etat(tmp_path / "e.json"), 1, 0, dossier=d) == []
