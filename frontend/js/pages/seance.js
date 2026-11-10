// Page d'une séance : en-tête (titre, client, date, durée), modification et suppression,
// puis la saisie : exercices choisis dans la liste et séries enregistrées une par une.
import { api } from "../api.js";
import {
    h, formatDate, formatDuree, formatCharge, aujourdhuiIso, toast, ouvrirModale, confirmer, etat, TYPES_EXERCICE,
} from "../ui.js";

export async function pageSeance(conteneur, id) {
    if (!/^\d+$/.test(id)) {
        afficherIntrouvable(conteneur);
        return;
    }

    let dernierChargement = 0;

    async function charger() {
        const numero = ++dernierChargement;
        let reponse, liste;
        try {
            // La liste d'exercices alimente « Ajouter un exercice »
            [reponse, liste] = await Promise.all([api(`/seances/${id}`), api("/exercices")]);
        } catch {
            if (numero !== dernierChargement || !conteneur.isConnected) return;
            conteneur.replaceChildren(fil(), etat("Impossible de contacter le serveur.",
                h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
            return;
        }
        // Réponse arrivée après un rechargement plus récent ou après avoir quitté la page : ignorée
        if (numero !== dernierChargement || !conteneur.isConnected) return;
        if (reponse.status === 404) {
            afficherIntrouvable(conteneur);
            return;
        }
        if (!reponse.ok) {
            conteneur.replaceChildren(fil(), etat("Le serveur a renvoyé une erreur.",
                h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
            return;
        }
        // Sans la liste d'exercices, seul « Ajouter un exercice » est indisponible : la séance reste lisible
        afficher(reponse.data, liste.ok && Array.isArray(liste.data) ? liste.data : null);
    }

    function afficher(seance, liste) {
        const zoneExercices = h("div", { class: "exercices-seance" });
        const vide = h("section", { class: "carte" },
            etat("Aucun exercice noté dans cette séance pour l'instant. Ajoutez-en un avec « Ajouter un exercice »."));
        if (seance.exercices.length === 0) zoneExercices.append(vide);
        else zoneExercices.append(...seance.exercices.map(carteExercice));

        // Un exercice ajouté arrive comme une nouvelle carte, sans recharger la page :
        // ce qui est en cours de saisie dans les autres cartes n'est pas perdu.
        function apresAjout(exercice) {
            vide.remove();
            const carte = carteExercice(exercice);
            zoneExercices.append(carte);
            carte.querySelector("input")?.focus();
        }

        conteneur.replaceChildren(
            fil(seance),
            h("header", { class: "entete-page entete-profil" },
                h("div", {},
                    h("h1", {}, seance.titre),
                    h("p", { class: "sous-titre infos-seance" },
                        h("span", {}, seance.athlete_nom),
                        h("span", {}, formatDate(seance.date_seance)),
                        seance.duree_min != null && h("span", {}, formatDuree(seance.duree_min)),
                    ),
                ),
                h("div", { class: "actions-entete" },
                    h("button", { type: "button", class: "btn", onClick: () => formulaireSeance(charger, { seance }) }, "Modifier la séance"),
                    h("button", { type: "button", class: "btn", onClick: () => supprimer(seance) }, "Supprimer la séance"),
                ),
            ),
            zoneExercices,
            ajoutExercice(seance, liste, apresAjout, charger),
        );
    }

    async function supprimer(seance) {
        const ok = await confirmer("Supprimer la séance",
            `Supprimer « ${seance.titre} » du ${formatDate(seance.date_seance)} ? Les exercices et séries notés dans cette séance seront aussi supprimés.`,
            "Supprimer");
        if (!ok) return;
        try {
            const reponse = await api(`/seances/${seance.id}`, { method: "DELETE" });
            if (reponse.ok || reponse.status === 404) {
                toast(reponse.ok ? "Séance supprimée." : "Cette séance avait déjà été supprimée.", reponse.ok ? "succes" : "erreur");
                location.hash = `#/clients/${seance.athlete_id}`;
            } else {
                toast("Le serveur a renvoyé une erreur. Réessayez.", "erreur");
            }
        } catch {
            toast("Impossible de contacter le serveur.", "erreur");
        }
    }

    conteneur.replaceChildren(fil(), etat("Chargement…"));
    await charger();
}

// Carte d'un exercice noté : ses séries enregistrées, puis la saisie de la série suivante.
// Chaque série est enregistrée dès « Ajouter la série » ; la suivante reprend le poids et le repos.
function carteExercice(exercice) {
    const avecCharge = exercice.type === "charge";
    const series = [...exercice.series];
    const derniere = () => series[series.length - 1];
    const idTitre = `exercice-${exercice.id}`;

    const compte = h("span", { class: "attenue" });
    const lignes = h("tbody", {});
    // Redessine les lignes après un ajout, une correction ou une suppression (numéros à jour)
    function dessinerLignes() {
        lignes.replaceChildren(...series.map((serie) => ligneSerie(serie, exercice, () => corriger(serie))));
    }
    const tableau = h("div", { class: "defilement" },
        h("table", { class: "tableau-series" },
            h("caption", { class: "visuellement-cache" }, `Séries de ${exercice.nom}`),
            h("thead", {}, h("tr", {},
                h("th", { scope: "col" }, "Série"),
                h("th", { scope: "col" }, "Poids"),
                h("th", { scope: "col" }, "Reps"),
                h("th", { scope: "col", class: "col-repos" }, "Repos"),
                h("th", { scope: "col" }, h("span", { class: "visuellement-cache" }, "État et actions")),
            )),
            lignes,
        ),
    );

    // Les exercices au poids du corps n'ont jamais de champ poids
    const poids = avecCharge ? h("input", {
        id: `poids-${exercice.id}`, type: "number", min: "0.1", max: "999.99", step: "any", inputmode: "decimal",
        value: derniere()?.poids_kg ?? "",
    }) : null;
    const reps = h("input", { id: `reps-${exercice.id}`, type: "number", min: "1", max: "999", step: "1", inputmode: "numeric", placeholder: "—" });
    const repos = h("input", {
        id: `repos-${exercice.id}`, type: "number", min: "0", max: "3600", step: "1", inputmode: "numeric",
        value: derniere()?.repos_sec ?? 90,
    });
    const numero = h("p", { class: "numero-saisie" });
    const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
    // Annonce la série enregistrée aux lecteurs d'écran ; à l'écran, c'est la nouvelle ligne cochée
    const statut = h("p", { class: "visuellement-cache", role: "status" });
    const valider = h("button", { type: "submit", class: "btn btn-primaire btn-serie" }, "Ajouter la série");

    function majEtat() {
        // 0 et 1 au singulier en français (« 0 série », comme sur la maquette)
        compte.textContent = series.length <= 1 ? `${series.length} série` : `${series.length} séries`;
        numero.textContent = `Série ${series.length + 1}`;
        tableau.hidden = series.length === 0;
    }

    const champ = (input, libelle) => h("div", { class: "champ" }, h("label", { for: input.id }, libelle), input);
    const form = h("form", { class: "saisie-serie", novalidate: true, "aria-label": `Nouvelle série de ${exercice.nom}` },
        numero,
        h("div", { class: "champs-serie" },
            poids && champ(poids, "Poids (kg)"),
            champ(reps, "Reps"),
            champ(repos, "Repos (s)"),
        ),
        erreur,
        statut,
        valider,
    );

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        erreur.textContent = "";
        statut.textContent = "";
        const champs = { poids, reps, repos };
        if (!validerSerie(champs, erreur)) return;
        valider.disabled = true;
        try {
            const reponse = await api(`/exercice-logs/${exercice.id}/series`, { method: "POST", body: corpsSerie(champs) });
            if (reponse.ok) {
                series.push(reponse.data);
                dessinerLignes();
                statut.textContent = `Série ${reponse.data.numero_serie} enregistrée.`;
                // Poids et repos restent pour la série suivante ; seules les reps sont à ressaisir
                reps.value = "";
                majEtat();
                reps.focus();
            } else {
                afficherErreurSerie(reponse, champs, erreur, "Cet exercice n'est plus dans la séance. Rechargez la page.");
            }
        } catch {
            erreur.textContent = "Impossible de contacter le serveur.";
        } finally {
            valider.disabled = false;
        }
    });

    // « Modifier » d'une ligne : correction de la série, ou suppression (les suivantes sont renumérotées)
    function corriger(serie) {
        formulaireCorrection(exercice, serie, {
            apresModification(corrigee) {
                // Par id et pas par objet : la ligne a pu être redessinée depuis l'ouverture de la fenêtre
                const i = series.findIndex((s) => s.id === corrigee.id);
                if (i !== -1) series[i] = corrigee;
                dessinerLignes();
                lignes.querySelector(`[data-serie="${corrigee.id}"]`)?.focus();
            },
            apresSuppression() {
                // Même renumérotation que le serveur : les séries suivantes descendent d'un numéro
                const i = series.findIndex((s) => s.id === serie.id);
                if (i === -1) return;
                series.splice(i, 1);
                for (const autre of series) {
                    if (autre.numero_serie > serie.numero_serie) autre.numero_serie -= 1;
                }
                dessinerLignes();
                majEtat();
                reps.focus();
            },
        });
    }

    dessinerLignes();
    majEtat();
    return h("section", { class: "carte carte-exercice", "aria-labelledby": idTitre },
        h("div", { class: "tete-exercice" },
            h("div", { class: "nom-exercice" },
                h("h2", { id: idTitre }, exercice.nom),
                h("span", { class: "etiquette" }, TYPES_EXERCICE[exercice.type] ?? exercice.type),
            ),
            compte,
        ),
        tableau,
        form,
    );
}

// Vérifications avant envoi, communes à la saisie et à la correction d'une série. champs = { poids, reps, repos }
// (poids vaut null au poids du corps). Écrit le message dans erreur et renvoie false si un champ ne va pas.
function validerSerie({ poids, reps, repos }, erreur) {
    let message = "", champ = null;
    if (poids && (!poids.value || poids.validity.badInput)) {
        [message, champ] = [poids.validity.badInput ? "Le poids doit être un nombre." : "Le poids est obligatoire.", poids];
    } else if (!reps.value) {
        [message, champ] = [reps.validity.badInput ? "Les répétitions doivent être un nombre." : "Le nombre de répétitions est obligatoire.", reps];
    } else if (repos.validity.badInput) {
        [message, champ] = ["Le repos doit être un nombre de secondes.", repos];
    }
    if (!champ) return true;
    erreur.textContent = message;
    champ.focus();
    return false;
}

function corpsSerie({ poids, reps, repos }) {
    const corps = { repetitions: reps.value, repos_sec: repos.value };
    if (poids) corps.poids_kg = poids.value;
    return corps;
}

// Message d'une réponse d'erreur de l'API pour une série (ajout ou correction) ; message404 dépend du cas.
function afficherErreurSerie(reponse, { poids, reps, repos }, erreur, message404) {
    const champ = reponse.status === 400 ? reponse.data?.field : null;
    if (champ === "poids_kg") {
        erreur.textContent = "Le poids doit être compris entre 0 et 1000 kg.";
        poids?.focus();
    } else if (champ === "repetitions") {
        erreur.textContent = "Les répétitions doivent être un nombre entier entre 1 et 999.";
        reps.focus();
    } else if (champ === "repos_sec") {
        erreur.textContent = "Le repos doit être un nombre entier de secondes, entre 0 et 3600.";
        repos.focus();
    } else if (reponse.status === 400) {
        erreur.textContent = poids ? "Le poids et les répétitions sont obligatoires." : "Les répétitions sont obligatoires.";
    } else if (reponse.status === 404) {
        erreur.textContent = message404;
    } else {
        erreur.textContent = "Le serveur a renvoyé une erreur. Réessayez.";
    }
}

function ligneSerie(serie, exercice, modifier) {
    return h("tr", {},
        h("td", { class: "attenue fort" }, serie.numero_serie),
        // Une charge reste sur une ligne (« 102,5 kg ») ; « Poids du corps » peut passer sur deux
        h("td", { class: exercice.type === "charge" ? "fort sans-coupure" : "fort" },
            exercice.type === "charge" ? formatCharge(serie.poids_kg) : "Poids du corps"),
        h("td", { class: "fort" }, serie.repetitions),
        h("td", { class: "attenue col-repos" }, `${serie.repos_sec} s`),
        h("td", { class: "a-droite actions-serie" },
            h("span", { class: "coche", role: "img", "aria-label": "Enregistrée" }, "✓"),
            h("button", {
                type: "button", class: "btn btn-ligne", "data-serie": serie.id,
                "aria-label": `Modifier la série ${serie.numero_serie} de ${exercice.nom}`,
                onClick: modifier,
            }, "Modifier"),
        ),
    );
}

// Fenêtre « Modifier la série » : mêmes champs qu'à la saisie (pas de poids au poids du corps),
// avec « Supprimer la série », qui demande confirmation.
function formulaireCorrection(exercice, serie, { apresModification, apresSuppression }) {
    const avecCharge = exercice.type === "charge";
    ouvrirModale(`Modifier la série ${serie.numero_serie} — ${exercice.nom}`, (fermer) => {
        const poids = avecCharge ? h("input", {
            id: "correction-poids", type: "number", min: "0.1", max: "999.99", step: "any", inputmode: "decimal", value: serie.poids_kg,
        }) : null;
        const reps = h("input", {
            id: "correction-reps", type: "number", min: "1", max: "999", step: "1", inputmode: "numeric", value: serie.repetitions,
        });
        const repos = h("input", {
            id: "correction-repos", type: "number", min: "0", max: "3600", step: "1", inputmode: "numeric", value: serie.repos_sec,
        });
        const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
        const valider = h("button", { type: "submit", class: "btn btn-primaire" }, "Enregistrer");

        // La confirmation s'ouvre par-dessus : « Annuler » y ramène à la correction, sans perdre ce qui a été tapé
        async function supprimer() {
            const ok = await confirmer("Supprimer la série",
                `Supprimer la série ${serie.numero_serie} de ${exercice.nom} ? Les séries suivantes seront renumérotées.`, "Supprimer");
            if (!ok) return;
            fermer();
            try {
                const reponse = await api(`/series/${serie.id}`, { method: "DELETE" });
                if (reponse.ok) {
                    toast("Série supprimée.");
                    apresSuppression();
                } else if (reponse.status === 404) {
                    toast("Cette série avait déjà été supprimée. Rechargez la page.", "erreur");
                } else {
                    toast("Le serveur a renvoyé une erreur. Réessayez.", "erreur");
                }
            } catch {
                toast("Impossible de contacter le serveur.", "erreur");
            }
        }

        const form = h("form", { class: "formulaire", novalidate: true },
            poids && h("label", { for: "correction-poids" }, "Poids (kg)"), poids,
            h("label", { for: "correction-reps" }, "Reps"), reps,
            h("label", { for: "correction-repos" }, "Repos (s)"), repos,
            erreur,
            h("div", { class: "actions actions-correction" },
                h("button", { type: "button", class: "btn btn-danger", onClick: supprimer }, "Supprimer la série"),
                h("button", { type: "button", class: "btn", onClick: fermer }, "Annuler"),
                valider,
            ),
        );

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            erreur.textContent = "";
            const champs = { poids, reps, repos };
            if (!validerSerie(champs, erreur)) return;
            valider.disabled = true;
            try {
                const reponse = await api(`/series/${serie.id}`, { method: "PUT", body: corpsSerie(champs) });
                if (reponse.ok) {
                    fermer();
                    toast("Série corrigée.");
                    apresModification(reponse.data);
                } else {
                    afficherErreurSerie(reponse, champs, erreur, "Cette série n'existe plus. Rechargez la page.");
                }
            } catch {
                erreur.textContent = "Impossible de contacter le serveur.";
            } finally {
                valider.disabled = false;
                // Fenêtre fermée pendant l'envoi : l'erreur part en message temporaire pour ne pas être perdue.
                if (!form.isConnected && erreur.textContent) {
                    toast(`Série non corrigée : ${erreur.textContent}`, "erreur");
                }
            }
        });

        queueMicrotask(() => reps.focus());
        return form;
    });
}

// « Ajouter un exercice » : seulement des exercices de la liste, et pas ceux déjà dans la séance.
// liste vaut null si elle n'a pas pu être chargée.
function ajoutExercice(seance, liste, apresAjout, recharger) {
    const dejaLa = new Set(seance.exercices.map((e) => e.exercice_id));
    const zone = h("section", { class: "carte", "aria-label": "Ajouter un exercice" });
    if (liste === null) {
        zone.append(etat("La liste d'exercices n'a pas pu être chargée.",
            h("button", { type: "button", class: "btn", onClick: recharger }, "Réessayer")));
        return zone;
    }
    const select = h("select", { id: "ajout-exercice" });
    const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
    const valider = h("button", { type: "submit", class: "btn btn-primaire" }, "+ Ajouter l'exercice");

    function remplir() {
        const disponibles = liste.filter((e) => !dejaLa.has(e.id));
        if (disponibles.length === 0) {
            zone.replaceChildren(etat("Tous les exercices de la liste sont déjà dans cette séance.",
                h("a", { href: "#/exercices", class: "btn" }, "Voir la liste d'exercices")));
            return;
        }
        select.replaceChildren(
            h("option", { value: "" }, "Choisir dans la liste…"),
            // replaceChildren (DOM) n'aplatit pas les tableaux, contrairement à h() : on déplie la liste
            ...disponibles.map((e) => h("option", { value: e.id }, `${e.nom} — ${TYPES_EXERCICE[e.type] ?? e.type}`)),
        );
    }

    const form = h("form", { class: "ajout-exercice", novalidate: true },
        h("div", { class: "champ" }, h("label", { for: "ajout-exercice" }, "Ajouter un exercice"), select),
        valider,
        erreur,
    );
    zone.append(form);

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        erreur.textContent = "";
        const choisi = liste.find((x) => String(x.id) === select.value);
        if (!choisi) {
            erreur.textContent = "Choisissez un exercice dans la liste.";
            select.focus();
            return;
        }
        valider.disabled = true;
        try {
            const reponse = await api(`/seances/${seance.id}/exercices`, { method: "POST", body: { exercice_id: choisi.id } });
            if (reponse.ok) {
                dejaLa.add(choisi.id);
                remplir();
                apresAjout({ id: reponse.data.id, exercice_id: choisi.id, nom: choisi.nom, type: choisi.type, series: [] });
            } else if (reponse.status === 409) {
                erreur.textContent = "Cet exercice est déjà dans la séance.";
            } else if (reponse.status === 400) {
                erreur.textContent = "Cet exercice n'est plus dans la liste.";
            } else if (reponse.status === 404) {
                erreur.textContent = "Cette séance n'existe plus.";
            } else {
                erreur.textContent = "Le serveur a renvoyé une erreur. Réessayez.";
            }
        } catch {
            erreur.textContent = "Impossible de contacter le serveur.";
        } finally {
            valider.disabled = false;
        }
    });

    remplir();
    return zone;
}

function afficherIntrouvable(conteneur) {
    conteneur.replaceChildren(
        fil(null, "Séance introuvable"),
        etat("Cette séance n'existe pas ou a été supprimée.", h("a", { href: "#/clients", class: "btn" }, "Retour aux clients")),
    );
}

// Fil d'Ariane : Clients / <client> / <séance — date>
function fil(seance = null, libelle = "…") {
    return h("nav", { class: "fil", "aria-label": "Fil d'Ariane" },
        h("a", { href: "#/clients" }, "Clients"),
        seance && h("span", { "aria-hidden": "true" }, "/"),
        seance && h("a", { href: `#/clients/${seance.athlete_id}` }, seance.athlete_nom),
        h("span", { "aria-hidden": "true" }, "/"),
        h("span", { "aria-current": "page" }, seance ? `${seance.titre} — ${formatDate(seance.date_seance).slice(0, 5)}` : libelle),
    );
}

// Fenêtre "Nouvelle séance" (avec athleteId : le client du profil) ou "Modifier la séance" (avec seance).
// Titre et date obligatoires (date du jour par défaut), durée facultative.
// En création, apresEnregistrement reçoit l'id de la nouvelle séance.
export function formulaireSeance(apresEnregistrement, { athleteId = null, seance = null }) {
    const modification = seance !== null;
    ouvrirModale(modification ? "Modifier la séance" : "Nouvelle séance", (fermer) => {
        const aujourdhui = aujourdhuiIso();
        // maxlength = longueur de la colonne seances.titre
        const titre = h("input", { id: "seance-titre", type: "text", required: true, maxlength: "200", autocomplete: "off", value: seance?.titre ?? "" });
        const date = h("input", { id: "seance-date", type: "date", required: true, max: aujourdhui, value: seance?.date_seance ?? aujourdhui });
        const duree = h("input", {
            id: "seance-duree", type: "number", min: "1", max: "600", step: "1", inputmode: "numeric", value: seance?.duree_min ?? "",
        });
        const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
        const valider = h("button", { type: "submit", class: "btn btn-primaire" }, modification ? "Enregistrer" : "Créer la séance");

        const form = h("form", { class: "formulaire", novalidate: true },
            h("label", { for: "seance-titre" }, "Titre"), titre,
            h("label", { for: "seance-date" }, "Date"), date,
            h("label", { for: "seance-duree" }, "Durée (min) ", h("span", { class: "facultatif" }, "(facultatif)")), duree,
            erreur,
            h("div", { class: "actions" },
                h("button", { type: "button", class: "btn", onClick: fermer }, "Annuler"),
                valider,
            ),
        );

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            erreur.textContent = "";
            if (!titre.value.trim()) {
                erreur.textContent = "Le titre est obligatoire.";
                titre.focus();
                return;
            }
            if (!date.value) {
                erreur.textContent = "La date est obligatoire.";
                date.focus();
                return;
            }
            if (duree.validity.badInput) {
                erreur.textContent = "La durée doit être un nombre de minutes.";
                duree.focus();
                return;
            }
            valider.disabled = true;
            const corps = { titre: titre.value, date_seance: date.value, duree_min: duree.value || null };
            try {
                const reponse = modification
                    ? await api(`/seances/${seance.id}`, { method: "PUT", body: corps })
                    : await api(`/athletes/${athleteId}/seances`, { method: "POST", body: corps });
                if (reponse.ok) {
                    fermer();
                    toast(modification ? "Séance modifiée." : "Séance créée.");
                    apresEnregistrement(reponse.data?.id);
                } else if (reponse.status === 400 && reponse.data?.field === "date_seance") {
                    erreur.textContent = "Cette date n'est pas valide (pas de séance à venir).";
                    date.focus();
                } else if (reponse.status === 400 && reponse.data?.field === "duree_min") {
                    erreur.textContent = "La durée doit être un nombre entier de minutes, entre 1 et 600.";
                    duree.focus();
                } else if (reponse.status === 400 && reponse.data?.field === "titre") {
                    erreur.textContent = "Le titre est trop long.";
                    titre.focus();
                } else if (reponse.status === 400) {
                    erreur.textContent = "Le titre et la date sont obligatoires.";
                } else if (reponse.status === 404) {
                    erreur.textContent = modification ? "Cette séance n'existe plus." : "Ce client n'existe plus.";
                } else {
                    erreur.textContent = "Le serveur a renvoyé une erreur. Réessayez.";
                }
            } catch {
                erreur.textContent = "Impossible de contacter le serveur.";
            } finally {
                valider.disabled = false;
                // Fenêtre fermée pendant l'envoi : l'erreur part en message temporaire pour ne pas être perdue.
                if (!form.isConnected && erreur.textContent) {
                    toast(`${modification ? "Séance non modifiée" : "Séance non créée"} : ${erreur.textContent}`, "erreur");
                }
            }
        });

        queueMicrotask(() => titre.focus());
        return form;
    });
}
