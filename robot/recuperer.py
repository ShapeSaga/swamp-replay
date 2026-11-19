"""Récupère les vidéos déposées par le PC de Chahine dans la release « videos ».

Le PC dépose pour chaque épisode : EP001.mp4, EP001.json (titre, légende, hashtags…), EP001.jpg (vignette Telegram)
et EP001_couverture.jpg (miniature). On copie dans episodes/ ceux que le robot ne connaît pas encore, mais
seulement s'il y a une place pour eux (créneau libre, ou place de test) : la réserve du PC n'est pas re-téléchargée
à chaque passage. L'orchestrateur les traite ensuite exactement comme les épisodes de Shape Saga.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .config import RACINE
from .etat import ENVOYE, Etat
from .hebergement import HebergeurGitHub

log = logging.getLogger(__name__)
NOM_FICHE = re.compile(r"^(EP\d{3,})\.json$")


def recuperer(heberg: HebergeurGitHub, etat: Etat, places_vraies: int, places_test: int,
              dossier: Path | None = None) -> list[str]:
    dossier = Path(dossier) if dossier else RACINE / "episodes"
    dossier.mkdir(parents=True, exist_ok=True)
    deja = {p.stem for p in dossier.glob("EP*.json")}
    # épisodes déjà présents localement (même passage) : ils occupent déjà une place
    for cle in deja:
        if cle in etat.episodes:
            continue
        try:
            test = json.loads((dossier / f"{cle}.json").read_text(encoding="utf-8")).get("test")
        except (OSError, ValueError):
            test = False
        if test: places_test -= 1
        else: places_vraies -= 1
    assets = heberg.lister()
    par_nom = {a["name"]: a for a in assets}
    pris = []
    for nom in sorted(par_nom):
        m = NOM_FICHE.match(nom)
        if not m:
            continue
        cle = m.group(1)
        if cle in etat.episodes or cle in deja or f"{cle}.mp4" not in par_nom:
            continue                                     # déjà connu, ou le PC n'a pas fini de déposer
        if places_vraies <= 0 and places_test <= 0:
            break
        fiche = dossier / f"{cle}.json.part"
        heberg.telecharger(par_nom[nom]["id"], fiche)
        try:
            test = bool(json.loads(fiche.read_text(encoding="utf-8")).get("test"))
        except ValueError:
            fiche.unlink(missing_ok=True)
            log.warning("Fiche illisible : %s", nom)
            continue
        if (test and places_test <= 0) or (not test and places_vraies <= 0):
            fiche.unlink(missing_ok=True)
            continue
        heberg.telecharger(par_nom[f"{cle}.mp4"]["id"], dossier / f"{cle}.mp4")
        for annexe in (f"{cle}.jpg", f"{cle}_couverture.jpg"):
            if annexe in par_nom:
                heberg.telecharger(par_nom[annexe]["id"], dossier / annexe)
        fiche.replace(dossier / nom)                     # la fiche en dernier : l'épisode est complet
        if test: places_test -= 1
        else: places_vraies -= 1
        pris.append(cle)
        log.info("Épisode récupéré du PC : %s%s", cle, " (test)" if test else "")
    return pris


def places(orchestrateur) -> tuple[int, int]:
    """(créneaux libres sur la période d'avance, places de test restantes)."""
    from . import planning
    o = orchestrateur
    _, libres = planning.places_libres(o.etat.episodes, o.maintenant(), o.conf["cadence"])
    attente_test = sum(1 for f in o.etat.episodes.values() if f["statut"] == ENVOYE and f.get("test"))
    return len(libres), max(0, o.conf["validation"]["max_en_attente"] - attente_test)
