// Point d'entrée : choisit la page à afficher selon l'adresse après le "#".
import { pageClients } from "./js/pages/clients.js";
import { pageProfil } from "./js/pages/profil.js";
import { pageExercices } from "./js/pages/exercices.js";

// "#/clients" → page Clients ; "#/clients/3" → profil du client 3 ; "#/exercices" → page Exercices.
const routes = {
    clients: pageClients,
    exercices: pageExercices,
};

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
