// L'adresse de ton API Flask
const API_URL = "http://localhost:5000";

// Fonction pour charger et afficher les athlètes
async function chargerAthletes() {
    try {
        const reponse = await fetch(`${API_URL}/athletes`);
        const athletes = await reponse.json();

        const listeHtml = document.getElementById("athletes-list");
        listeHtml.innerHTML = "";

        athletes.forEach(athlete => {
            const li = document.createElement("li");
            li.className = "list-group-item d-flex justify-content-between align-items-center p-3";
            
            li.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="avatar me-3 bg-primary text-white">${athlete.nom.charAt(0) }</div>
                    <div>
                        <h6 class="mb-0">${athlete.nom}</h6>
                        <small class="text-muted">Poids : ${athlete.poids_kg || 0} kg</small>
                    </div>
                </div>
                </div>
                <button class="btn btn-sm btn-outline-primary">Voir</button>
            `;
            listeHtml.appendChild(li);
        });

    } catch (erreur) {
        console.error("Erreur lors du chargement des athlètes :", erreur);
        document.getElementById("athletes-list").innerHTML = 
            `<li class="list-group-item text-danger">Erreur de connexion à l'API</li>`;
    }
}

// On lance la fonction dès que la page est chargée
document.addEventListener("DOMContentLoaded", () => {
    chargerAthletes();
});

// Écouteur sur le formulaire de nouvelle séance
document.getElementById("form-seance").addEventListener("submit", async (e) => {
    e.preventDefault(); 

    // On récupère les valeurs tapées par le coach
    const athleteId = document.getElementById("input-athlete-id").value;
    const titre = document.getElementById("input-titre").value;
    const dateSeance = document.getElementById("input-date").value;
    const duree = document.getElementById("input-duree").value;

    const nouvelleSeance = {
        athlete_id: Number.parseInt(athleteId, 10),
        titre: (titre || "").trim(),
        date_seance: dateSeance,
        duree_min: parseInt(duree)
    };

    try {
        //  On envoie les valeurs au serveur avec la méthode POST
        const reponse = await fetch(`${API_URL}/seances`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(nouvelleSeance) 
        });

        if (reponse.ok) {
            alert("✅ Séance enregistrée avec succès !");
            
            const modaleElement = document.getElementById('modalNouvelleSeance');
            const modaleBootstrap = bootstrap.Modal.getInstance(modaleElement);
            modaleBootstrap.hide();
            
            document.getElementById("form-seance").reset();

        } else {
            alert("❌ Erreur de l'API lors de l'enregistrement.");
        }
    } catch (erreur) {
        console.error("Erreur réseau :", erreur);
        alert("Impossible de contacter le serveur Flask.");
    }
});