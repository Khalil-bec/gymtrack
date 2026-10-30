// Profil d'un client : infos, résumé, poids de corps (graphique ou tableau) et pesées.
import { api } from "../api.js";
import {
    h, formatDate, formatDateLongue, formatMoisAnnee, formatPoids, formatEvolution,
    aujourdhuiIso, toast, ouvrirModale, confirmer, etat, initiales,
} from "../ui.js";

export async function pageProfil(conteneur, id) {
    // Graphique de cette page : détruit avant d'en dessiner un autre et quand on quitte la page,
    // sinon Chart.js le garde en mémoire avec ses écouteurs.
    let graphique = null;
    window.addEventListener("hashchange", () => graphique?.destroy(), { once: true });

    if (!/^\d+$/.test(id)) {
        afficherIntrouvable(conteneur);
        return;
    }

    // Vue du poids de corps choisie par l'utilisateur, gardée entre deux rechargements
    let vueTableau = false;
    let dernierChargement = 0;

    async function charger() {
        const numero = ++dernierChargement;
        let profil, pesees;
        try {
            [profil, pesees] = await Promise.all([api(`/athletes/${id}`), api(`/athletes/${id}/pesees`)]);
        } catch {
            if (numero !== dernierChargement || !conteneur.isConnected) return;
            conteneur.replaceChildren(fil("…"), etat("Impossible de contacter le serveur.",
                h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
            return;
        }
        // Réponse arrivée après un rechargement plus récent ou après avoir quitté la page : ignorée
        if (numero !== dernierChargement || !conteneur.isConnected) return;
        if (profil.status === 404) {
            afficherIntrouvable(conteneur);
            return;
        }
        if (!profil.ok || !pesees.ok || !Array.isArray(pesees.data)) {
            conteneur.replaceChildren(fil("…"), etat("Le serveur a renvoyé une erreur.",
                h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
            return;
        }
        afficher(profil.data, pesees.data);
    }

    function afficher(client, pesees) {
        graphique?.destroy();
        graphique = null;

        const zonePoids = h("div", {});
        const basculer = h("button", { type: "button", class: "lien" });
        function dessinerPoids() {
            // Sans Chart.js (CDN bloqué ou hors ligne), les pesées restent lisibles en tableau
            const graphiqueDispo = typeof window.Chart === "function";
            basculer.textContent = vueTableau ? "Voir le graphique" : "Voir en tableau";
            basculer.hidden = pesees.length === 0 || !graphiqueDispo;
            graphique?.destroy();
            graphique = null;
            if (pesees.length === 0) {
                zonePoids.replaceChildren(etat("Aucune pesée pour l'instant. Ajoutez-en une avec « Ajouter une pesée »."));
            } else if (vueTableau || !graphiqueDispo) {
                zonePoids.replaceChildren(tableauPesees(pesees, supprimer));
            } else {
                const canvas = h("canvas", { role: "img", "aria-label": descriptionGraphique(pesees) });
                zonePoids.replaceChildren(h("div", { class: "zone-graphique" }, canvas));
                graphique = graphiquePoids(canvas, pesees);
            }
        }
        basculer.addEventListener("click", () => {
            vueTableau = !vueTableau;
            dessinerPoids();
        });

        const sousTitre = [client.email, `client depuis ${formatMoisAnnee(client.created_at)}`].filter(Boolean).join(" · ");
        conteneur.replaceChildren(
            fil(client.nom),
            h("header", { class: "entete-page entete-profil" },
                h("div", { class: "identite" },
                    h("div", { class: "avatar avatar-grand", "aria-hidden": "true" }, initiales(client.nom)),
                    h("div", {}, h("h1", {}, client.nom), h("p", { class: "sous-titre" }, sousTitre)),
                ),
                h("button", { type: "button", class: "btn", onClick: () => formulairePesee(id, charger) }, "Ajouter une pesée"),
            ),
            h("section", { class: "tuiles", "aria-label": "Résumé" },
                tuile("Dernière séance", formatDateLongue(client.derniere_seance)),
                tuile("Séances sur 4 semaines", client.seances_4_semaines),
                tuile("Poids actuel", formatPoids(client.poids_actuel),
                    client.evolution_4_semaines === null ? null : `${formatEvolution(client.evolution_4_semaines)} en 4 sem.`),
            ),
            h("section", { class: "carte", "aria-labelledby": "titre-poids" },
                h("div", { class: "carte-tete" },
                    h("h2", { id: "titre-poids" }, "Poids de corps"),
                    h("span", { class: "attenue" }, pesees.length === 1 ? "1 pesée" : `${pesees.length} pesées`),
                ),
                h("p", { class: "legende" }, "Pesées (kg)"),
                zonePoids,
                basculer,
            ),
        );
        dessinerPoids();
    }

    async function supprimer(pesee) {
        const ok = await confirmer("Supprimer la pesée",
            `Supprimer la pesée du ${formatDate(pesee.date_pesee)} (${formatPoids(pesee.poids_kg)}) ?`, "Supprimer");
        if (!ok) return;
        try {
            const reponse = await api(`/pesees/${pesee.id}`, { method: "DELETE" });
            if (reponse.ok) toast("Pesée supprimée.");
            else if (reponse.status === 404) toast("Cette pesée avait déjà été supprimée.", "erreur");
            else toast("Le serveur a renvoyé une erreur. Réessayez.", "erreur");
        } catch {
            toast("Impossible de contacter le serveur.", "erreur");
            return;
        }
        charger();
    }

    conteneur.replaceChildren(fil("…"), etat("Chargement…"));
    await charger();
}

function afficherIntrouvable(conteneur) {
    conteneur.replaceChildren(
        fil("Client introuvable"),
        etat("Ce client n'existe pas ou n'existe plus.", h("a", { href: "#/clients", class: "btn" }, "Retour aux clients")),
    );
}

// Fil d'Ariane : Clients / <nom du client>
function fil(nom) {
    return h("nav", { class: "fil", "aria-label": "Fil d'Ariane" },
        h("a", { href: "#/clients" }, "Clients"),
        h("span", { "aria-hidden": "true" }, "/"),
        h("span", { "aria-current": "page" }, nom),
    );
}

function tuile(libelle, valeur, detail) {
    return h("div", { class: "carte tuile" },
        h("p", { class: "tuile-libelle" }, libelle),
        h("p", { class: "tuile-valeur" }, valeur, detail && h("span", { class: "tuile-detail" }, detail)),
    );
}

function descriptionGraphique(pesees) {
    const premiere = pesees[0];
    const derniere = pesees[pesees.length - 1];
    if (pesees.length === 1) return `Poids de corps : ${formatPoids(premiere.poids_kg)} le ${formatDate(premiere.date_pesee)}`;
    return `Poids de corps : de ${formatPoids(premiere.poids_kg)} le ${formatDate(premiere.date_pesee)} `
        + `à ${formatPoids(derniere.poids_kg)} le ${formatDate(derniere.date_pesee)}`;
}

// Courbe en pointillés des pesées (couleurs et polices du thème Corail).
function graphiquePoids(canvas, pesees) {
    const { Chart } = window;
    const styles = getComputedStyle(document.documentElement);
    const couleur = (nom) => styles.getPropertyValue(nom).trim();
    const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
    const axe = {
        ticks: { color: couleur("--attenue"), font: { family: "Barlow", size: 13 } },
        grid: { color: couleur("--bord") },
        border: { display: false },
    };
    return new Chart(canvas, {
        type: "line",
        data: {
            labels: pesees.map((p) => formatDate(p.date_pesee).slice(0, 5)),
            datasets: [{
                data: pesees.map((p) => p.poids_kg),
                borderColor: "#cbd5e1",
                borderWidth: 3,
                borderDash: [8, 6],
                pointBackgroundColor: couleur("--carte"),
                pointBorderColor: "#cbd5e1",
                pointBorderWidth: 2.5,
                pointRadius: 5,
                pointHoverRadius: 7,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: matchMedia("(prefers-reduced-motion: reduce)").matches ? false : undefined,
            plugins: {
                legend: { display: false },
                tooltip: {
                    displayColors: false,
                    callbacks: {
                        title: (points) => formatDate(pesees[points[0].dataIndex].date_pesee),
                        label: (point) => formatPoids(point.parsed.y),
                    },
                },
            },
            scales: {
                x: { ...axe, grid: { display: false } },
                y: { ...axe, ticks: { ...axe.ticks, callback: (valeur) => nombre.format(valeur) } },
            },
        },
    });
}

// Vue tableau du graphique : les mêmes pesées, la plus récente en premier, avec suppression.
function tableauPesees(pesees, supprimer) {
    const lignes = [...pesees].reverse().map((pesee) =>
        h("tr", {},
            h("td", { class: "attenue" }, formatDate(pesee.date_pesee)),
            h("td", { class: "fort" }, formatPoids(pesee.poids_kg)),
            h("td", { class: "a-droite" },
                h("button", {
                    type: "button", class: "lien",
                    "aria-label": `Supprimer la pesée du ${formatDate(pesee.date_pesee)}`,
                    onClick: () => supprimer(pesee),
                }, "Supprimer"),
            ),
        ),
    );
    return h("div", { class: "defilement" },
        h("table", { class: "tableau-compact" },
            h("caption", { class: "visuellement-cache" }, "Pesées (kg), de la plus récente à la plus ancienne"),
            h("thead", {}, h("tr", {},
                h("th", { scope: "col" }, "Date"),
                h("th", { scope: "col" }, "Poids"),
                h("th", { scope: "col" }, h("span", { class: "visuellement-cache" }, "Actions")),
            )),
            h("tbody", {}, lignes),
        ),
    );
}

// Fenêtre "Ajouter une pesée" : date (aujourd'hui par défaut) + poids.
function formulairePesee(id, apresAjout) {
    ouvrirModale("Ajouter une pesée", (fermer) => {
        const aujourdhui = aujourdhuiIso();
        const date = h("input", { id: "pesee-date", type: "date", required: true, max: aujourdhui, value: aujourdhui });
        const poids = h("input", {
            id: "pesee-poids", type: "number", required: true, min: "0.1", max: "999.99", step: "0.1", inputmode: "decimal",
        });
        const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
        const valider = h("button", { type: "submit", class: "btn btn-primaire" }, "Ajouter");

        const form = h("form", { class: "formulaire", novalidate: true },
            h("label", { for: "pesee-date" }, "Date"), date,
            h("label", { for: "pesee-poids" }, "Poids (kg)"), poids,
            erreur,
            h("div", { class: "actions" },
                h("button", { type: "button", class: "btn", onClick: fermer }, "Annuler"),
                valider,
            ),
        );

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            erreur.textContent = "";
            if (!date.value) {
                erreur.textContent = "La date est obligatoire.";
                date.focus();
                return;
            }
            if (!poids.value) {
                erreur.textContent = poids.validity.badInput ? "Le poids doit être un nombre." : "Le poids est obligatoire.";
                poids.focus();
                return;
            }
            valider.disabled = true;
            try {
                const reponse = await api(`/athletes/${id}/pesees`, {
                    method: "POST",
                    body: { date_pesee: date.value, poids_kg: poids.value },
                });
                if (reponse.ok) {
                    fermer();
                    toast("Pesée ajoutée.");
                    apresAjout();
                } else if (reponse.status === 400 && reponse.data?.field === "date_pesee") {
                    erreur.textContent = "Cette date n'est pas valide.";
                    date.focus();
                } else if (reponse.status === 400) {
                    erreur.textContent = "Le poids doit être compris entre 0 et 1000 kg.";
                    poids.focus();
                } else if (reponse.status === 404) {
                    erreur.textContent = "Ce client n'existe plus.";
                } else {
                    erreur.textContent = "Le serveur a renvoyé une erreur. Réessayez.";
                }
            } catch {
                erreur.textContent = "Impossible de contacter le serveur.";
            } finally {
                valider.disabled = false;
                // Fenêtre fermée pendant l'envoi : l'erreur part en message temporaire pour ne pas être perdue.
                if (!form.isConnected && erreur.textContent) {
                    toast(`Pesée non ajoutée : ${erreur.textContent}`, "erreur");
                }
            }
        });

        queueMicrotask(() => poids.focus());
        return form;
    });
}
