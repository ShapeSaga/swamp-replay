"""Alerte « stock bas » : créneaux vides sur 7 jours et aucune vidéo prête (fabrique du PC muette)."""
import json

from tests.test_flux import monde  # noqa: F401  (même faux monde)


def messages(s):
    return [a for a in s.appels if a[1].endswith("sendMessage")]


def test_alerte_si_aucune_video(monde, tmp_path):  # noqa: F811
    o, s = monde
    for p in o.dossier.glob("EP*"):
        p.unlink()
    o.envoyer_nouveaux()
    assert "stock-bas" in o.etat.donnees["alertes"]
    o.envoyer_nouveaux()                                # pas de répétition immédiate
    assert len(messages(s)) == 1


def test_pas_d_alerte_si_videos_pretes(monde):  # noqa: F811
    o, s = monde
    o.envoyer_nouveaux()
    assert "stock-bas" not in o.etat.donnees["alertes"]
