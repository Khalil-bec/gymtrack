// Point d'entrée : choisit la page à afficher selon l'adresse après le "#".
import { h } from "./js/ui.js";
import { pageClients } from "./js/pages/clients.js";
import { pageProfil } from "./js/pages/profil.js";

// "#/clients" → page Clients ; "#/clients/3" → profil du client 3 ; "#/exercices" → page Exercices (à venir).
const routes = {
    clients: pageClients,
    exercices: pageExercices,
};

function pageExercices(conteneur) {
    conteneur.replaceChildren(
        h("header", { class: "entete-page" }, h("div", {}, h("h1", {}, "Exercices"))),
        h("div", { class: "etat" }, h("p", {}, "La liste d'exercices arrive bientôt.")),
    );
}

function afficher() {
    const [section, id] = location.hash.replace(/^#\/?/, "").split("/");
    const nom = routes[section] ? section : "clients";

    document.querySelectorAll("[data-nav]").forEach((lien) => {
        if (lien.dataset.nav === nom) lien.setAttribute("aria-current", "page");
        else lien.removeAttribute("aria-current");
    });

    // Chaque affichage repart d'un conteneur neuf : une page encore en chargement
    // (réponse lente de l'API) écrit dans l'ancien, déjà retiré, et ne gêne pas la nouvelle.
    const conteneur = document.createElement("div");
    conteneur.id = "page";
    conteneur.className = "page";
    conteneur.tabIndex = -1;
    document.getElementById("page").replaceWith(conteneur);

    const page = nom === "clients" && id ? pageProfil(conteneur, id) : routes[nom](conteneur);
    Promise.resolve(page).catch((erreur) => console.error(erreur));
    conteneur.focus({ preventScroll: true });
}

window.addEventListener("hashchange", afficher);
afficher();
