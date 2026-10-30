// Page d'accueil : la liste des clients du coach.
import { api } from "../api.js";
import { h, formatDate, toast, ouvrirModale, etat } from "../ui.js";

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
                    h("span", { class: "nom" }, c.nom),
                ),
            ),
            h("td", { class: "attenue" }, formatDate(c.derniere_seance)),
            h("td", {}, c.seances_4_semaines),
        ),
    );
    return h("section", { class: "carte carte-tableau" },
        h("div", { class: "defilement" },
            h("table", {},
                h("thead", {}, h("tr", {},
                    h("th", { scope: "col" }, "Client"),
                    h("th", { scope: "col" }, "Dernière séance"),
                    h("th", { scope: "col" }, "Séances (4 sem.)"),
                )),
                h("tbody", {}, lignes),
            ),
        ),
    );
}

function initiales(nom) {
    return nom.split(/\s+/).filter(Boolean).slice(0, 2).map((mot) => Array.from(mot)[0].toUpperCase()).join("");
}

// Fenêtre "Nouveau client" : nom obligatoire, email facultatif.
function formulaireClient(apresCreation) {
    ouvrirModale("Nouveau client", (fermer) => {
        const nom = h("input", { id: "client-nom", type: "text", required: true, autocomplete: "off" });
        const email = h("input", { id: "client-email", type: "email", autocomplete: "off" });
        const erreur = h("p", { class: "erreur-formulaire", role: "alert" });
        const valider = h("button", { type: "submit", class: "btn btn-primaire" }, "Ajouter");

        const form = h("form", { class: "formulaire", novalidate: true },
            h("label", { for: "client-nom" }, "Nom"), nom,
            h("label", { for: "client-email" }, "Email ", h("span", { class: "facultatif" }, "(facultatif)")), email,
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
            valider.disabled = true;
            try {
                const reponse = await api("/athletes", {
                    method: "POST",
                    body: { nom: nom.value, email: email.value },
                });
                if (reponse.ok) {
                    fermer();
                    toast("Client ajouté.");
                    apresCreation();
                } else if (reponse.status === 409) {
                    erreur.textContent = "Cet email est déjà utilisé par un autre client.";
                    email.focus();
                } else if (reponse.status === 400 && reponse.data?.field === "email") {
                    erreur.textContent = "Cet email n'est pas valide.";
                    email.focus();
                } else if (reponse.status === 400) {
                    erreur.textContent = "Le nom est obligatoire.";
                    nom.focus();
                } else {
                    erreur.textContent = "Le serveur a renvoyé une erreur. Réessayez.";
                }
            } catch {
                erreur.textContent = "Impossible de contacter le serveur.";
            } finally {
                valider.disabled = false;
                // Fenêtre fermée (Échap, Annuler) pendant l'envoi : l'erreur part en message temporaire pour ne pas être perdue.
                if (!form.isConnected && erreur.textContent) {
                    toast(`Client non ajouté : ${erreur.textContent}`, "erreur");
                }
            }
        });

        queueMicrotask(() => nom.focus());
        return form;
    });
}
