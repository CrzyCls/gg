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


def lire_timers(page):
    page.goto(URL)
    page.locator("input[type=text]").first.fill(PSEUDO)
    page.get_by_role("button", name="Continuer").click()
    page.wait_for_timeout(4000)

    resultats = {}
    for carte in page.locator("a", has_text="Site #").all():
        texte = carte.inner_text()
        site = SITE.search(texte)
        if not site:
            continue
        t = TIMER.search(texte)
        secondes = int(t[1]) * 3600 + int(t[2]) * 60 + int(t[3]) if t else 0
        resultats[f"Site #{site[1]}"] = secondes
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
