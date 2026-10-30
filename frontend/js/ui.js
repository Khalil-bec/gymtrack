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

// "Khalil Becheikh" → "KB". Array.from découpe par caractère (un emoji en début de nom reste entier).
export function initiales(nom) {
    return nom.split(/\s+/).filter(Boolean).slice(0, 2).map((mot) => Array.from(mot)[0].toUpperCase()).join("");
}

// "2026-03-22" → "22/03/2026" ; vide → "—". Pas de new Date() pour éviter les décalages de fuseau.
export function formatDate(iso) {
    if (!iso) return "—";
    const [annee, mois, jour] = iso.slice(0, 10).split("-");
    return `${jour}/${mois}/${annee}`;
}

const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"];

// "2026-03-22" → "22 mars 2026" ; vide → "—".
export function formatDateLongue(iso) {
    if (!iso) return "—";
    const [annee, mois, jour] = iso.slice(0, 10).split("-");
    return `${Number(jour)} ${MOIS[Number(mois) - 1]} ${annee}`;
}

// "2026-02-03T10:00:00" → "février 2026".
export function formatMoisAnnee(iso) {
    const [annee, mois] = iso.slice(0, 10).split("-");
    return `${MOIS[Number(mois) - 1]} ${annee}`;
}

// Date du jour au format "AAAA-MM-JJ", à l'heure locale (valeur par défaut des champs date).
export function aujourdhuiIso() {
    const d = new Date();
    return [d.getFullYear(), d.getMonth() + 1, d.getDate()].map((n) => String(n).padStart(2, "0")).join("-");
}

const nombre = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 2 });

// 80.5 → "80,5 kg" ; vide → "—".
export function formatPoids(kg) {
    return kg === null || kg === undefined ? "—" : `${nombre.format(kg)} kg`;
}

// -1.9 → "−1,9 kg" ; 0.4 → "+0,4 kg" ; vide → "—".
export function formatEvolution(kg) {
    if (kg === null || kg === undefined) return "—";
    const signe = kg > 0 ? "+" : kg < 0 ? "−" : "";
    return `${signe}${nombre.format(Math.abs(kg))} kg`;
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

// Fenêtre de confirmation (à la place de confirm()). Renvoie une promesse : true si l'utilisateur confirme.
export function confirmer(titre, message, libelleAction) {
    return new Promise((resoudre) => {
        let reponse = false;
        const dialog = ouvrirModale(titre, (fermer) =>
            h("div", { class: "formulaire" },
                h("p", { class: "message-confirmation" }, message),
                h("div", { class: "actions" },
                    h("button", { type: "button", class: "btn", onClick: fermer }, "Annuler"),
                    h("button", { type: "button", class: "btn btn-primaire", onClick: () => { reponse = true; fermer(); } }, libelleAction),
                ),
            ),
        );
        dialog.addEventListener("close", () => resoudre(reponse));
    });
}
