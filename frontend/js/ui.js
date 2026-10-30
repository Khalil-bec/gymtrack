// Petits outils d'interface partagés par toutes les pages.

// Crée un élément. Le texte passe toujours par textContent : une valeur venant de l'API
// (un nom contenant "<b>" par exemple) s'affiche comme du texte et ne s'exécute jamais.
export function h(tag, attrs = {}, ...enfants) {
    const el = document.createElement(tag);
    for (const [cle, valeur] of Object.entries(attrs)) {
        if (valeur === undefined || valeur === null || valeur === false) continue;
        if (cle.startsWith("on")) el.addEventListener(cle.slice(2).toLowerCase(), valeur);
        else if (cle === "class") el.className = valeur;
        else el.setAttribute(cle, valeur === true ? "" : valeur);
    }
    for (const enfant of enfants.flat()) {
        if (enfant === undefined || enfant === null || enfant === false) continue;
        el.append(enfant instanceof Node ? enfant : document.createTextNode(String(enfant)));
    }
    return el;
}

// "2026-03-22" → "22/03/2026" ; vide → "—". Pas de new Date() pour éviter les décalages de fuseau.
export function formatDate(iso) {
    if (!iso) return "—";
    const [annee, mois, jour] = iso.slice(0, 10).split("-");
    return `${jour}/${mois}/${annee}`;
}

// Message temporaire en bas de l'écran, à la place de alert().
export function toast(message, type = "succes") {
    const zone = document.getElementById("toasts");
    const el = h("div", { class: `toast toast-${type}` }, message);
    zone.append(el);
    setTimeout(() => el.remove(), 4000);
}

let compteurModales = 0;

// Ouvre une fenêtre de formulaire (<dialog>). `contenu` reçoit une fonction fermer().
export function ouvrirModale(titre, construireContenu) {
    const idTitre = `modale-titre-${++compteurModales}`;
    const dialog = h("dialog", { class: "modale", "aria-labelledby": idTitre });
    const fermer = () => dialog.close();
    dialog.append(
        h("div", { class: "modale-tete" },
            h("h2", { id: idTitre }, titre),
            h("button", { type: "button", class: "btn-icone", "aria-label": "Fermer", onClick: fermer }, "×"),
        ),
        construireContenu(fermer),
    );
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    dialog.showModal();
    return dialog;
}

// Zone d'état (chargement, vide, erreur) affichée à la place d'un contenu.
export function etat(message, action) {
    return h("div", { class: "etat" }, h("p", {}, message), action);
}
