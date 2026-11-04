// Point d'entrée : choisit la page à afficher selon l'adresse après le "#".
import { pageClients } from "./js/pages/clients.js";
import { pageProfil } from "./js/pages/profil.js";
import { pageExercices } from "./js/pages/exercices.js";
import { pageSeance } from "./js/pages/seance.js";

// "#/clients" → page Clients ; "#/clients/3" → profil du client 3 ; "#/seances/42" → séance 42 ;
// "#/exercices" → page Exercices.
const routes = {
    clients: pageClients,
    exercices: pageExercices,
};
// Pages qui affichent un élément ("#/<section>/<id>"), et l'entrée du menu qu'elles allument
const pagesDetail = {
    clients: { page: pageProfil, menu: "clients" },
    seances: { page: pageSeance, menu: "clients" },
};

function afficher() {
    const [section, id] = location.hash.replace(/^#\/?/, "").split("/");
    const detail = id ? pagesDetail[section] : undefined;
    const nom = detail ? detail.menu : routes[section] ? section : "clients";

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

    const page = detail ? detail.page(conteneur, id) : routes[nom](conteneur);
    Promise.resolve(page).catch((erreur) => console.error(erreur));
    conteneur.focus({ preventScroll: true });
}

window.addEventListener("hashchange", afficher);
afficher();
