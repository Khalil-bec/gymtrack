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
    chargerSeances();
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
        duree_min: Number.parseInt(duree, 10) || null
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



// Charger les séances
async function chargerSeances() {
    try {
        const reponse = await fetch(`${API_URL}/seances`);
        const seances = await reponse.json();
        console.log(seances);
        const listeHtml = document.querySelector("#seances-table tbody");
        listeHtml.innerHTML = "";
        seances.forEach((seance) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td class="ps-3"><span class="text-muted fw-bold">${new Date(seance.date_seance).toLocaleDateString() || "N/A"}</span></td>
                <td><strong>${seance.athlete_nom}</strong></td>
                <td>${seance.titre}</td>
                <td>${seance.duree_min} min</td>
                <td>
                    <button type="button" class="btn btn-sm btn-light text-primary btn-detail-seance">
                        <i class="bi bi-eye"></i> Détails
                    </button>
                </td>
            `;
            tr.querySelector(".btn-detail-seance").addEventListener("click", () => {
                voirDetailsSeance(
                    seance.id,
                    seance.titre || "",
                    String(seance.date_seance ?? ""),
                    Number(seance.duree_min) || 0,
                    seance.athlete_nom || ""
                );
            });
            listeHtml.appendChild(tr);
        });
    } catch (erreur) {
        console.error("Erreur lors du chargement des séances :", erreur);
        document.getElementById("seances-list").innerHTML = `<li class="list-group-item text-danger">Erreur de connexion à l'API</li>`;
    }
}

// Fonction pour voir les détails d'une séance (résumé depuis la liste + logs depuis GET /seances/:id)
async function voirDetailsSeance(seanceId, titre, dateSeance, dureeMin, athleteNom) {
    try {
        const reponse = await fetch(`${API_URL}/seances/${seanceId}`);
        if (!reponse.ok) {
            throw new Error(`HTTP ${reponse.status}`);
        }
        const lignes = await reponse.json();

        document.getElementById("detail-titre").textContent = titre || "Séance";
        document.getElementById("detail-date").textContent = dateSeance || "—";
        document.getElementById("detail-duree").textContent =
            dureeMin != null && dureeMin !== "" ? `${dureeMin} min` : "—";
        document.getElementById("detail-athlete").textContent = athleteNom || "—";

        const zone = document.getElementById("detail-exercices");
        if (!Array.isArray(lignes) || lignes.length === 0) {
            zone.innerHTML =
                '<p class="text-muted small mb-0">Aucun exercice enregistré pour cette séance.</p>';
        } else {
            zone.innerHTML = `
                <p class="text-muted small fw-bold mb-2">EXERCICES & SÉRIES</p>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Exercice</th>
                                <th>Série</th>
                                <th>Poids (kg)</th>
                                <th>Reps</th>
                                <th>Repos (s)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${lignes
                                .map(
                                    (l) => `
                                <tr>
                                    <td>${escapeHtml(l.exercice)}</td>
                                    <td>${l.numero_serie ?? "—"}</td>
                                    <td>${l.poids_kg ?? "—"}</td>
                                    <td>${l.repetitions ?? "—"}</td>
                                    <td>${l.repos_sec ?? "—"}</td>
                                </tr>`
                                )
                                .join("")}
                        </tbody>
                    </table>
                </div>`;
        }

        const modaleElement = document.getElementById("modalDetailsSeance");
        bootstrap.Modal.getOrCreateInstance(modaleElement).show();
    } catch (erreur) {
        console.error("Erreur lors de la récupération des détails de la séance :", erreur);
        alert("Impossible de récupérer les détails de la séance.");
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
}
document.addEventListener('DOMContentLoaded', function() {

    
    // 1. Cibler le canvas
    const ctx = document.getElementById('volumeChart').getContext('2d');

    // 2. Créer le graphique
    const volumeChart = new Chart(ctx, {
        type: 'line', // Type de graphique : 'line', 'bar', 'doughnut', etc.
        data: {
            // Les étiquettes sur l'axe X (ex: les jours ou les semaines)
            labels: ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
            datasets: [{
                label: 'Volume (kg)',
                data: [1200, 1900, 800, 2100, 1500, 2800, 0], // Tes données
                borderColor: '#4f46e5', // Ta couleur primaire (bleu/violet)
                backgroundColor: 'rgba(79, 70, 229, 0.1)', // Fond transparent sous la courbe
                borderWidth: 3,
                tension: 0.4, // Rend la courbe "douce" et arrondie
                fill: true, // Remplissage sous la courbe
                pointBackgroundColor: '#ffffff',
                pointBorderColor: '#4f46e5',
                pointRadius: 4      
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // Permet au graphique de s'adapter au conteneur (les 300px définis dans le HTML)
            plugins: {
                legend: {
                    display: false // On cache la légende si c'est assez explicite avec le titre de la carte
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#f1f5f9' // Couleur de la grille (assortie à ton design)
                    }
                },
                x: {
                    grid: {
                        display: false // On cache la grille verticale pour un look plus épuré
                    }
                }
            }
        }
    });
});