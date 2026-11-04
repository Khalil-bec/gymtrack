// Page d'une séance : en-tête (titre, client, date, durée), modification et suppression.
// La saisie des exercices et des séries viendra s'ajouter sous l'en-tête.
import { api } from "../api.js";
import { h, formatDate, formatDuree, aujourdhuiIso, toast, ouvrirModale, confirmer, etat } from "../ui.js";

export async function pageSeance(conteneur, id) {
    if (!/^\d+$/.test(id)) {
        afficherIntrouvable(conteneur);
        return;
    }

    let dernierChargement = 0;

    async function charger() {
        const numero = ++dernierChargement;
        let reponse;
        try {
            reponse = await api(`/seances/${id}`);
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
        afficher(reponse.data);
    }

    function afficher(seance) {
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
            // Le détail des exercices et séries s'affichera ici avec la saisie des séances
            h("section", { class: "carte" }, etat(
                seance.nb_exercices === 0 ? "Aucun exercice noté dans cette séance pour l'instant."
                    : seance.nb_exercices === 1 ? "1 exercice noté dans cette séance."
                        : `${seance.nb_exercices} exercices notés dans cette séance.`,
            )),
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
