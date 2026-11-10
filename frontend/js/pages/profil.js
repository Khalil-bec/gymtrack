// Profil d'un client : infos, résumé, progression par exercice et poids de corps (graphique ou tableau), séances.
import { api } from "../api.js";
import {
    h, formatDate, formatDateLongue, formatMoisAnnee, formatPoids, formatEvolution, formatDuree, formatCharge,
    aujourdhuiIso, toast, ouvrirModale, confirmer, etat, initiales,
} from "../ui.js";
import { formulaireClient } from "./clients.js";
import { formulaireSeance } from "./seance.js";

export async function pageProfil(conteneur, id) {
    // Graphiques de cette page : détruits avant d'en dessiner d'autres et quand on quitte la page,
    // sinon Chart.js les garde en mémoire avec leurs écouteurs.
    let graphique = null;
    let graphiqueProgression = null;
    window.addEventListener("hashchange", () => {
        graphique?.destroy();
        graphiqueProgression?.destroy();
    }, { once: true });

    if (!/^\d+$/.test(id)) {
        afficherIntrouvable(conteneur);
        return;
    }

    // Vues et exercice choisis par l'utilisateur, gardés entre deux rechargements
    let vueTableau = false;
    let vueTableauProgression = false;
    let exerciceChoisi = null;
    let dernierChargement = 0;

    async function charger() {
        const numero = ++dernierChargement;
        let profil, pesees, seances, progression;
        try {
            [profil, pesees, seances, progression] = await Promise.all([
                api(`/athletes/${id}`), api(`/athletes/${id}/pesees`), api(`/athletes/${id}/seances`),
                api(`/athletes/${id}/progression`),
            ]);
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
        // La progression n'est qu'une carte : si elle échoue, le reste du profil s'affiche quand même
        const listes = [pesees, seances];
        if (!profil.ok || !listes.every((reponse) => reponse.ok && Array.isArray(reponse.data))) {
            conteneur.replaceChildren(fil("…"), etat("Le serveur a renvoyé une erreur.",
                h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
            return;
        }
        const exercices = progression.ok && Array.isArray(progression.data) ? progression.data : null;
        afficher(profil.data, pesees.data, seances.data, exercices);
    }

    // exercices = null : la progression n'a pas pu être chargée
    function afficher(client, pesees, seances, exercicesOuErreur) {
        const erreurProgression = exercicesOuErreur === null;
        const exercices = exercicesOuErreur ?? [];
        graphique?.destroy();
        graphique = null;
        graphiqueProgression?.destroy();
        graphiqueProgression = null;

        // Progression : l'exercice choisi reste choisi après un rechargement, s'il a encore des séries ;
        // sinon, l'exercice travaillé le plus récemment
        if (!exercices.some((exercice) => exercice.exercice_id === exerciceChoisi)) {
            exerciceChoisi = plusRecent(exercices)?.exercice_id ?? null;
        }
        const zoneProgression = h("div", {});
        const legendeProgression = h("p", { class: "legende" });
        const basculerProgression = h("button", { type: "button", class: "lien" });
        const choix = h("select", { id: "choix-exercice", onChange: () => {
            exerciceChoisi = Number(choix.value);
            dessinerProgression();
        } }, exercices.map((exercice) => h("option", {
            value: exercice.exercice_id, selected: exercice.exercice_id === exerciceChoisi,
        }, exercice.nom)));
        function dessinerProgression() {
            const graphiqueDispo = typeof window.Chart === "function";
            const exercice = exercices.find((e) => e.exercice_id === exerciceChoisi);
            basculerProgression.textContent = vueTableauProgression ? "Voir le graphique" : "Voir en tableau";
            basculerProgression.hidden = !exercice || !graphiqueDispo;
            legendeProgression.hidden = !exercice;
            graphiqueProgression?.destroy();
            graphiqueProgression = null;
            if (erreurProgression) {
                zoneProgression.replaceChildren(etat("Impossible de charger la progression.",
                    h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
                return;
            }
            if (!exercice) {
                zoneProgression.replaceChildren(etat("Aucune série notée pour l'instant. "
                    + "La progression apparaît dès qu'une séance contient des séries."));
                return;
            }
            legendeProgression.textContent = exercice.type === "charge"
                ? "Charge la plus lourde par séance (kg)"
                : "Répétitions max en une série, par séance (poids du corps)";
            if (vueTableauProgression || !graphiqueDispo) {
                zoneProgression.replaceChildren(tableauProgression(exercice));
            } else {
                const canvas = h("canvas", { role: "img", "aria-label": descriptionProgression(exercice) });
                zoneProgression.replaceChildren(h("div", { class: "zone-graphique" }, canvas));
                graphiqueProgression = graphiqueExercice(canvas, exercice);
            }
        }
        basculerProgression.addEventListener("click", () => {
            vueTableauProgression = !vueTableauProgression;
            dessinerProgression();
        });

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
                h("div", { class: "actions-entete" },
                    h("button", { type: "button", class: "btn", onClick: () => formulaireClient(charger, client) }, "Modifier"),
                    h("button", { type: "button", class: "btn", onClick: () => formulairePesee(id, charger) }, "Ajouter une pesée"),
                    h("button", {
                        type: "button", class: "btn btn-primaire",
                        // La séance créée s'ouvre tout de suite : c'est là qu'on la remplit
                        onClick: () => formulaireSeance((idSeance) => { location.hash = `#/seances/${idSeance}`; }, { athleteId: id }),
                    }, "+ Nouvelle séance"),
                ),
            ),
            h("section", { class: "tuiles", "aria-label": "Résumé" },
                tuile("Dernière séance", formatDateLongue(client.derniere_seance)),
                tuile("Séances sur 4 semaines", client.seances_4_semaines),
                tuile("Poids actuel", formatPoids(client.poids_actuel),
                    client.evolution_4_semaines === null ? null : `${formatEvolution(client.evolution_4_semaines)} en 4 sem.`),
            ),
            h("div", { class: "graphiques" },
                h("section", { class: "carte", "aria-labelledby": "titre-progression" },
                    h("div", { class: "carte-tete" },
                        h("h2", { id: "titre-progression" }, "Progression"),
                        exercices.length > 0 && h("div", { class: "choix-exercice" },
                            h("label", { for: "choix-exercice" }, "Exercice"), choix),
                    ),
                    legendeProgression,
                    zoneProgression,
                    basculerProgression,
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
            ),
            h("section", { class: "carte carte-tableau", "aria-labelledby": "titre-seances" },
                h("div", { class: "carte-tete carte-tete-tableau" },
                    h("h2", { id: "titre-seances" }, "Séances"),
                    h("span", { class: "attenue" }, seances.length === 1 ? "1 séance" : `${seances.length} séances`),
                ),
                seances.length === 0
                    ? etat("Aucune séance pour l'instant. Créez-en une avec « Nouvelle séance ».")
                    : tableauSeances(seances),
            ),
        );
        dessinerPoids();
        dessinerProgression();
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

// Couleurs, polices et axes du thème Corail, communs aux deux graphiques.
function themeGraphique() {
    const styles = getComputedStyle(document.documentElement);
    const couleur = (nom) => styles.getPropertyValue(nom).trim();
    const axe = {
        ticks: { color: couleur("--attenue"), font: { family: "Barlow", size: 13 } },
        grid: { color: couleur("--bord") },
        border: { display: false },
    };
    const animation = matchMedia("(prefers-reduced-motion: reduce)").matches ? false : undefined;
    return { couleur, axe, animation };
}

// Courbe en pointillés des pesées : elle se distingue de la progression (trait plein) autrement que par la couleur.
function graphiquePoids(canvas, pesees) {
    const { Chart } = window;
    const { couleur, axe, animation } = themeGraphique();
    const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
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
            animation,
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

// Exercice dont le dernier point est le plus récent (à date égale, le premier dans l'ordre alphabétique).
function plusRecent(exercices) {
    const derniere = (exercice) => exercice.points[exercice.points.length - 1].date_seance;
    return exercices.reduce((choisi, exercice) => (!choisi || derniere(exercice) > derniere(choisi) ? exercice : choisi), null);
}

// Valeur d'un point de progression : la charge (avec charge) ou les répétitions (poids du corps).
const valeurPoint = (exercice, point) => (exercice.type === "charge" ? point.poids_kg : point.repetitions);

// "82,5 kg × 6 reps" ou "11 reps"
function formatMeilleureSerie(exercice, point) {
    const reps = point.repetitions === 1 ? "1 rep" : `${point.repetitions} reps`;
    return exercice.type === "charge" ? `${formatCharge(point.poids_kg)} × ${reps}` : reps;
}

function descriptionProgression(exercice) {
    const premier = exercice.points[0];
    const dernier = exercice.points[exercice.points.length - 1];
    const valeur = (point) => (exercice.type === "charge" ? formatCharge(point.poids_kg) : `${point.repetitions} reps`);
    if (exercice.points.length === 1) {
        return `${exercice.nom} : ${valeur(premier)} le ${formatDate(premier.date_seance)}`;
    }
    return `${exercice.nom} : de ${valeur(premier)} le ${formatDate(premier.date_seance)} `
        + `à ${valeur(dernier)} le ${formatDate(dernier.date_seance)}`;
}

// Courbe en trait plein de la meilleure série par séance, le dernier point plein (comme sur la maquette).
function graphiqueExercice(canvas, exercice) {
    const { Chart } = window;
    const { couleur, axe, animation } = themeGraphique();
    const accent = couleur("--accent");
    const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
    const { points } = exercice;
    const charge = exercice.type === "charge";
    return new Chart(canvas, {
        type: "line",
        data: {
            labels: points.map((p) => formatDate(p.date_seance).slice(0, 5)),
            datasets: [{
                data: points.map((p) => valeurPoint(exercice, p)),
                borderColor: accent,
                borderWidth: 3,
                pointBackgroundColor: points.map((_, i) => (i === points.length - 1 ? accent : couleur("--carte"))),
                pointBorderColor: accent,
                pointBorderWidth: 2.5,
                pointRadius: points.map((_, i) => (i === points.length - 1 ? 6 : 5)),
                pointHoverRadius: 7,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation,
            plugins: {
                legend: { display: false },
                tooltip: {
                    displayColors: false,
                    callbacks: {
                        title: (items) => formatDate(points[items[0].dataIndex].date_seance),
                        label: (item) => formatMeilleureSerie(exercice, points[item.dataIndex]),
                    },
                },
            },
            scales: {
                x: { ...axe, grid: { display: false } },
                y: {
                    ...axe,
                    // Le titre de l'axe dit ce qu'on mesure : des kilos ou des répétitions
                    title: { display: true, text: charge ? "kg" : "reps", color: couleur("--attenue"), font: axe.ticks.font },
                    ticks: { ...axe.ticks, precision: charge ? undefined : 0, callback: (valeur) => nombre.format(valeur) },
                },
            },
        },
    });
}

// Vue tableau de la progression : les mêmes points, le plus récent en premier, chacun menant à sa séance.
function tableauProgression(exercice) {
    const charge = exercice.type === "charge";
    const lignes = [...exercice.points].reverse().map((point) =>
        h("tr", {},
            h("td", { class: "attenue" }, formatDate(point.date_seance)),
            charge && h("td", { class: "fort" }, formatCharge(point.poids_kg)),
            h("td", { class: charge ? undefined : "fort" }, point.repetitions),
            h("td", { class: "a-droite" },
                h("a", {
                    class: "lien-action", href: `#/seances/${point.seance_id}`,
                    "aria-label": `Ouvrir la séance du ${formatDate(point.date_seance)}`,
                }, "Ouvrir"),
            ),
        ),
    );
    const legende = charge ? "charge la plus lourde par séance et ses répétitions" : "répétitions max en une série, par séance";
    return h("div", { class: "defilement" },
        h("table", { class: "tableau-compact" },
            h("caption", { class: "visuellement-cache" }, `${exercice.nom} : ${legende}, de la plus récente à la plus ancienne`),
            h("thead", {}, h("tr", {},
                h("th", { scope: "col" }, "Date"),
                charge && h("th", { scope: "col" }, "Charge"),
                h("th", { scope: "col" }, "Reps"),
                h("th", { scope: "col" }, h("span", { class: "visuellement-cache" }, "Actions")),
            )),
            h("tbody", {}, lignes),
        ),
    );
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

// Séances du client, la plus récente en premier (ordre donné par l'API).
function tableauSeances(seances) {
    const lignes = seances.map((seance) =>
        h("tr", {},
            h("td", { class: "attenue" }, formatDate(seance.date_seance)),
            h("td", { class: "fort clair" }, seance.titre),
            h("td", {}, seance.nb_exercices),
            h("td", {}, formatDuree(seance.duree_min)),
            h("td", { class: "a-droite" },
                h("a", {
                    class: "lien-action", href: `#/seances/${seance.id}`,
                    "aria-label": `Ouvrir la séance « ${seance.titre} » du ${formatDate(seance.date_seance)}`,
                }, "Ouvrir"),
            ),
        ),
    );
    return h("div", { class: "defilement" },
        h("table", { class: "tableau-seances" },
            h("thead", {}, h("tr", {},
                h("th", { scope: "col" }, "Date"),
                h("th", { scope: "col" }, "Titre"),
                h("th", { scope: "col" }, "Exercices"),
                h("th", { scope: "col" }, "Durée"),
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
