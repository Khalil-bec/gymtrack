// Tous les appels à l'API passent par ici.
import { API_URL } from "../config.js";

// Renvoie { ok, status, data }. Lève une erreur seulement si le serveur est injoignable,
// pour que chaque page distingue "erreur de l'API" (400, 409…) et "pas de réseau".
export async function api(path, { method = "GET", body } = {}) {
    const options = { method, headers: {} };
    if (body !== undefined) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }
    const reponse = await fetch(`${API_URL}${path}`, options);
    const data = await reponse.json().catch(() => null);
    return { ok: reponse.ok, status: reponse.status, data };
}
