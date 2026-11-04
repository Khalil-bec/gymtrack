// Page Exercices : la liste partagée par toutes les séances, filtrable par type. On peut seulement ajouter.
import { api } from "../api.js";
import { h, toast, ouvrirModale, etat } from "../ui.js";

const TYPES = { charge: "Avec charge", poids_du_corps: "Poids du corps" };
const FILTRES = [["tous", "Tous"], ["charge", "Avec charge"], ["poids_du_corps", "Poids du corps"]];

export async function pageExercices(conteneur) {
    const zone = h("div", {});
    // null tant que la liste n'est pas chargée (ou si le dernier chargement a échoué) : un clic sur
    // un filtre ne doit pas remplacer « Chargement… » ou l'erreur par un faux « aucun exercice ».
    let exercices = null;
    // Filtre choisi, gardé quand la liste se recharge après un ajout
    let filtre = "tous";

    const boutonsFiltre = FILTRES.map(([valeur, libelle]) =>
        h("button", {
            type: "button", class: "filtre", "aria-pressed": String(valeur === filtre),
            onClick: () => {
                filtre = valeur;
                boutonsFiltre.forEach((bouton, i) => bouton.setAttribute("aria-pressed", String(FILTRES[i][0] === filtre)));
                if (exercices) afficherListe();
            },
        }, libelle),
    );

    conteneur.replaceChildren(
        h("header", { class: "entete-page" },
            h("div", {}, h("h1", {}, "Exercices"), h("p", { class: "sous-titre" }, "La liste partagée par toutes les séances")),
            h("button", { type: "button", class: "btn btn-primaire", onClick: () => formulaireExercice(charger) }, "+ Nouvel exercice"),
        ),
        h("div", { class: "filtres", role: "group", "aria-label": "Filtrer par type" }, boutonsFiltre),
        zone,
    );

    // Numéro du dernier chargement lancé : une réponse plus ancienne qui arrive après est ignorée.
    let dernierChargement = 0;

    async function charger() {
        const numero = ++dernierChargement;
        exercices = null;
        zone.replaceChildren(etat("Chargement…"));
        let reponse;
        try {
            reponse = await api("/exercices");
        } catch {
            if (numero !== dernierChargement) return;
            zone.replaceChildren(etat("Impossible de contacter le serveur.",
                h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
            return;
        }
        if (numero !== dernierChargement) return;
        if (!reponse.ok || !Array.isArray(reponse.data)) {
            zone.replaceChildren(etat("Le serveur a renvoyé une erreur.",
                h("button", { type: "button", class: "btn", onClick: charger }, "Réessayer")));
            return;
        }
        exercices = reponse.data;
        afficherListe();
    }

    function afficherListe() {
        const visibles = filtre === "tous" ? exercices : exercices.filter((e) => e.type === filtre);
        if (exercices.length === 0) {
            zone.replaceChildren(etat("Aucun exercice pour l'instant. Ajoutez-en un avec « Nouvel exercice »."));
        } else if (visibles.length === 0) {
            zone.replaceChildren(etat(`Aucun exercice « ${TYPES[filtre]} » pour l'instant.`));
        } else {
            zone.replaceChildren(tableauExercices(visibles));
        }
    }

    await charger();
}

function tableauExercices(exercices) {
    const lignes = exercices.map((e) =>
        h("tr", {},
            h("td", { class: "fort clair" }, e.nom),
            h("td", {}, h("span", { class: "etiquette" }, TYPES[e.type] ?? e.type)),
            h("td", { class: "attenue" }, e.nb_seances === 1 ? "1 séance" : `${e.nb_seances} séances`),
        ),
    );
    return h("section", { class: "carte carte-tableau tableau-exercices" },
        h("div", { class: "defilement" },
            h("table", {},
                h("thead", {}, h("tr", {},
                    h("th", { scope: "col" }, "Nom"),
                    h("th", { scope: "col" }, "Type"),
                    h("th", { scope: "col" }, "Utilisé dans"),
                )),
                h("tbody", {}, lignes),
            ),
        ),
    );
}

// Fenêtre "Nouvel exercice" : nom + type. Pas de type par défaut : il ne pourra plus être changé.
function formulaireExercice(apresAjout) {
    ouvrirModale("Nouvel exercice", (fermer) => {
        // maxlength = longueur de la colonne exercices.nom
        const nom = h("input", { id: "exercice-nom", type: "text", required: true, maxlength: "100", autocomplete: "off" });
        const radios = Object.entries(TYPES).map(([valeur, libelle]) =>
            h("label", { class: "choix" },
                h("input", { type: "radio", name: "exercice-type", value: valeur, required: true }), libelle),
        );
        const types = h("fieldset", { class: "groupe-choix" }, h("legend", {}, "Type"), radios);
        const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
        const valider = h("button", { type: "submit", class: "btn btn-primaire" }, "Ajouter");

        const form = h("form", { class: "formulaire", novalidate: true },
            h("label", { for: "exercice-nom" }, "Nom"), nom,
            types,
            erreur,
            h("div", { class: "actions" },
                h("button", { type: "button", class: "btn", onClick: fermer }, "Annuler"),
                valider,
            ),
        );
        const typeChoisi = () => form.querySelector('input[name="exercice-type"]:checked')?.value;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            erreur.textContent = "";
            if (!nom.value.trim()) {
                erreur.textContent = "Le nom est obligatoire.";
                nom.focus();
                return;
            }
            if (!typeChoisi()) {
                erreur.textContent = "Choisissez un type : avec charge ou poids du corps.";
                radios[0].querySelector("input").focus();
                return;
            }
            valider.disabled = true;
            try {
                const reponse = await api("/exercices", { method: "POST", body: { nom: nom.value, type: typeChoisi() } });
                if (reponse.ok) {
                    fermer();
                    toast("Exercice ajouté.");
                    apresAjout();
                } else if (reponse.status === 409) {
                    erreur.textContent = "Cet exercice existe déjà (les majuscules et les accents ne comptent pas).";
                    nom.focus();
                } else if (reponse.status === 400 && reponse.data?.field === "type") {
                    erreur.textContent = "Choisissez un type : avec charge ou poids du corps.";
                } else if (reponse.status === 400 && reponse.data?.field === "nom") {
                    erreur.textContent = "Le nom est trop long.";
                    nom.focus();
                } else if (reponse.status === 400) {
                    erreur.textContent = "Le nom et le type sont obligatoires.";
                } else {
                    erreur.textContent = "Le serveur a renvoyé une erreur. Réessayez.";
                }
            } catch {
                erreur.textContent = "Impossible de contacter le serveur.";
            } finally {
                valider.disabled = false;
                // Fenêtre fermée pendant l'envoi : l'erreur part en message temporaire pour ne pas être perdue.
                if (!form.isConnected && erreur.textContent) {
                    toast(`Exercice non ajouté : ${erreur.textContent}`, "erreur");
                }
            }
        });

        queueMicrotask(() => nom.focus());
        return form;
    });
}
