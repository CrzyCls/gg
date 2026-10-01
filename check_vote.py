"""
Vérifie une seule fois les timers de vote PixelSMP et envoie une notif ntfy
si un site est disponible. Conçu pour être relancé périodiquement par
GitHub Actions (pas de boucle infinie).

Variables d'environnement attendues : PSEUDO, TOPIC
"""
import json
import os
import re

import requests
from playwright.sync_api import sync_playwright

PSEUDO = os.environ["PSEUDO"]
TOPIC = os.environ["TOPIC"]
URL = "https://pixelsmp.fr/vote"
ETAT_FICHIER = "state.json"

TIMER = re.compile(r"(\d{2}):(\d{2}):(\d{2})")
SITE = re.compile(r"Site #(\d+)")


def notifier(message):
    requests.post(f"https://ntfy.sh/{TOPIC}", data=message.encode("utf-8"))
    print(message)


def fermer_bandeau_cookies(page):
    """Ferme une éventuelle bannière RGPD qui bloquerait les clics suivants."""
    textes_possibles = [
        "Tout accepter", "J'accepte", "Accepter", "Accepter tout",
        "Accept all", "Accept",
    ]
    for texte in textes_possibles:
        bouton = page.get_by_role("button", name=texte)
        try:
            if bouton.first.is_visible(timeout=1500):
                bouton.first.click()
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def lire_timers(page):
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    fermer_bandeau_cookies(page)

    page.locator("input[type=text]").first.fill(PSEUDO)
    page.locator("input[type=text]").first.press("Enter")

    # Attend que le premier compte à rebours (ou le texte "Cliquer pour voter")
    # soit bien affiché avant de lire la page, plutôt qu'une pause fixe trop courte.
    try:
        page.wait_for_selector("text=/\\d{2}:\\d{2}:\\d{2}/", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    resultats = {}
    for carte in page.locator("a", has_text="Site #").all():
        texte = carte.inner_text()
        site = SITE.search(texte)
        if not site:
            continue
        t = TIMER.search(texte)
        if t:
            # Calcule les secondes et retire 120 secondes (2 minutes) d'avance
            secondes_reelles = int(t[1]) * 3600 + int(t[2]) * 60 + int(t[3])
            secondes = max(0, secondes_reelles - 120)
        else:
            secondes = 0
        resultats[f"Site #{site[1]}"] = secondes

    if not resultats or all(v == 0 for v in resultats.values()):
        # Rien de fiable détecté : on garde une preuve visuelle pour diagnostiquer.
        page.screenshot(path="debug.png", full_page=True)

    return resultats


def charger_etat():
    if os.path.exists(ETAT_FICHIER):
        with open(ETAT_FICHIER, encoding="utf-8") as f:
            return json.load(f)
    return {}


def sauver_etat(etat):
    with open(ETAT_FICHIER, "w", encoding="utf-8") as f:
        json.dump(etat, f)


def main():
    etat = charger_etat()

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        timers = lire_timers(page)
        navigateur.close()

    print("Timers :", timers)

    if timers and all(v == 0 for v in timers.values()):
        print("⚠️ Tous les timers sont à 0 en même temps : lecture suspecte, pas de notif envoyée.")
        return

    for site, secondes in timers.items():
        deja_notifie = etat.get(site, False)
        if secondes == 0 and not deja_notifie:
            notifier(f"🗝️ Tu peux voter sur {site} !")
            etat[site] = True
        elif secondes > 0:
            etat[site] = False

    sauver_etat(etat)


if __name__ == "__main__":
    main()
