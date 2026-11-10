// Page d'accueil : la liste des clients du coach.
import { api } from "../api.js";
import { h, formatDate, formatPoids, formatEvolution, toast, ouvrirModale, etat, initiales } from "../ui.js";

export async function pageClients(conteneur) {
    const sousTitre = h("p", { class: "sous-titre" }, "");
    const zone = h("div", {});
    conteneur.replaceChildren(
        h("header", { class: "entete-page" },
            h("div", {}, h("h1", {}, "Clients"), sousTitre),
            h("button", { type: "button", class: "btn btn-primaire", onClick: () => formulaireClient(charger) }, "+ Nouveau client"),
        ),
        zone,
    );

    // Numéro du dernier chargement lancé : une réponse plus ancienne qui arrive après est ignorée.
    let dernierChargement = 0;

    async function charger() {
        const numero = ++dernierChargement;
        zone.replaceChildren(etat("Chargement…"));
        let reponse;
        try {
            reponse = await api("/athletes");
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
        const clients = reponse.data;
        sousTitre.textContent = clients.length === 1 ? "1 client suivi" : `${clients.length} clients suivis`;
        if (clients.length === 0) {
            zone.replaceChildren(etat("Aucun client pour l'instant. Ajoutez le premier avec « Nouveau client »."));
            return;
        }
        zone.replaceChildren(tableauClients(clients));
    }

    await charger();
}

function tableauClients(clients) {
    const lignes = clients.map((c) =>
        h("tr", {},
            h("td", {},
                h("div", { class: "cellule-client" },
                    h("div", { class: "avatar", "aria-hidden": "true" }, initiales(c.nom)),
                    h("a", { class: "nom", href: `#/clients/${c.id}` }, c.nom),
                ),
            ),
            h("td", { class: "attenue" }, formatDate(c.derniere_seance)),
            h("td", {}, c.seances_4_semaines),
            h("td", { class: "fort" }, formatPoids(c.poids_actuel)),
            h("td", { class: "attenue" }, formatEvolution(c.evolution_4_semaines)),
            h("td", { class: "a-droite" },
                h("a", { class: "lien-action", href: `#/clients/${c.id}`, "aria-label": `Voir le profil de ${c.nom}` }, "Voir le profil")),
        ),
    );
    return h("section", { class: "carte carte-tableau" },
        h("div", { class: "defilement" },
            h("table", {},
                h("thead", {}, h("tr", {},
                    h("th", { scope: "col" }, "Client"),
                    h("th", { scope: "col" }, "Dernière séance"),
                    h("th", { scope: "col" }, "Séances (4 sem.)"),
                    h("th", { scope: "col" }, "Poids"),
                    h("th", { scope: "col" }, "Évolution (4 sem.)"),
                    h("th", { scope: "col" }, h("span", { class: "visuellement-cache" }, "Actions")),
                )),
                h("tbody", {}, lignes),
            ),
        ),
    );
}

// Fenêtre "Nouveau client" (nom obligatoire ; email et poids de départ facultatifs)
// ou, si on lui passe un client, "Modifier le client" : nom et email pré-remplis, sans poids
// (le poids se corrige par les pesées).
export function formulaireClient(apresEnregistrement, client = null) {
    const modification = client !== null;
    ouvrirModale(modification ? "Modifier le client" : "Nouveau client", (fermer) => {
        // maxlength = longueur des colonnes athletes.nom et athletes.email
        const nom = h("input", {
            id: "client-nom", type: "text", required: true, maxlength: "100", autocomplete: "off", value: client?.nom ?? "",
        });
        const email = h("input", { id: "client-email", type: "email", maxlength: "150", autocomplete: "off", value: client?.email ?? "" });
        const poids = modification ? null : h("input", {
            id: "client-poids", type: "number", min: "0.1", max: "999.99", step: "0.1", inputmode: "decimal",
        });
        const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
        const valider = h("button", { type: "submit", class: "btn btn-primaire" }, modification ? "Enregistrer" : "Ajouter");

        const form = h("form", { class: "formulaire", novalidate: true },
            h("label", { for: "client-nom" }, "Nom"), nom,
            h("label", { for: "client-email" }, "Email ", h("span", { class: "facultatif" }, "(facultatif)")), email,
            poids && h("label", { for: "client-poids" }, "Poids de départ (kg) ", h("span", { class: "facultatif" }, "(facultatif)")),
            poids,
            erreur,
            h("div", { class: "actions" },
                h("button", { type: "button", class: "btn", onClick: fermer }, "Annuler"),
                valider,
            ),
        );

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            erreur.textContent = "";
            if (!nom.value.trim()) {
                erreur.textContent = "Le nom est obligatoire.";
                nom.focus();
                return;
            }
            if (poids?.validity.badInput) {
                erreur.textContent = "Le poids doit être un nombre.";
                poids.focus();
                return;
            }
            valider.disabled = true;
            try {
                const reponse = modification
                    ? await api(`/athletes/${client.id}`, { method: "PUT", body: { nom: nom.value, email: email.value } })
                    : await api("/athletes", {
                        method: "POST",
                        body: { nom: nom.value, email: email.value, poids_kg: poids.value || null },
                    });
                if (reponse.ok) {
                    fermer();
                    toast(modification ? "Client modifié." : "Client ajouté.");
                    apresEnregistrement();
                } else if (reponse.status === 409) {
                    erreur.textContent = "Cet email est déjà utilisé par un autre client.";
                    email.focus();
                } else if (reponse.status === 400 && reponse.data?.field === "email") {
                    erreur.textContent = "Cet email n'est pas valide.";
                    email.focus();
                } else if (reponse.status === 400 && reponse.data?.field === "nom") {
                    erreur.textContent = "Le nom est trop long.";
                    nom.focus();
                } else if (reponse.status === 400 && poids && reponse.data?.field === "poids_kg") {
                    erreur.textContent = "Le poids doit être compris entre 0 et 1000 kg.";
                    poids.focus();
                } else if (reponse.status === 400) {
                    erreur.textContent = "Le nom est obligatoire.";
                    nom.focus();
                } else if (reponse.status === 404) {
                    // Client supprimé entre-temps : on ferme et on recharge, la page affiche « introuvable »
                    fermer();
                    toast("Ce client n'existe plus.", "erreur");
                    apresEnregistrement();
                } else {
                    erreur.textContent = "Le serveur a renvoyé une erreur. Réessayez.";
                }
            } catch {
                erreur.textContent = "Impossible de contacter le serveur.";
            } finally {
                valider.disabled = false;
                // Fenêtre fermée (Échap, Annuler) pendant l'envoi : l'erreur part en message temporaire pour ne pas être perdue.
                if (!form.isConnected && erreur.textContent) {
                    toast(`${modification ? "Client non modifié" : "Client non ajouté"} : ${erreur.textContent}`, "erreur");
                }
            }
        });

        queueMicrotask(() => nom.focus());
        return form;
    });
}
